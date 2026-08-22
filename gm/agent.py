"""The GM agent: the model-facing half of the intent protocol.

Two calls per mechanical turn and zero for a turn that is only talk. Call 1 is expensive
and carries the world; call 2 is handed a small packet of resolved facts and asked only to
say them well.

Everything the model produces is checked in code before it touches the engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings

from rules.intents import Intent, IntentError, find_outcome_claims

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
        cfg = settings.MODELS[role]
        self.model = cfg["model"]
        self.host = cfg["host"]
        self._echoes = None

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
        """
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events)
        base = prompts.call_one_messages(brief, history, player_input)
        messages = base

        attempts: list[Attempt] = []
        rejections: list[str] = []

        for n in range(max_attempts):
            reply = client.chat(messages, self.model, self.host, as_json=True,
                                temperature=0.8 if n == 0 else 0.5)
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
                intents = self.engine.validate(
                    judgement.fill_obvious_targets(data.get("intents"),
                                                   self.engine.scene))
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
            if not verdict.ok and n < max_attempts - 1:
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
                    if n < max_attempts - 1:
                        messages = _with_correction(base, reply.text, str(exc))
                        continue
                    raise

            # Check 4 is the only one that gets a targeted repair, because the narration
            # around the claim is worth keeping.
            narration = judgement.name_refs(narration, self.engine.scene)
            narration, claim_repairs, repair_attempts = self._repair_outcome_claims(narration)
            attempts.extend(repair_attempts)
            narration, prose_repairs, prose_attempts = self.polish(
                narration, earlier=recent_narration or [],
                min_chars=narration_mod.MIN_SCENE_CHARS,
                player_input=player_input, scene_brief=brief)
            attempts.extend(prose_attempts)

            return TurnPlan(narration=narration, intents=intents,
                            suggestions=_suggestions(data),
                            attempts=attempts,
                            repairs=repairs + claim_repairs + prose_repairs,
                            rejections=rejections)

        raise IntentError(
            "the GM could not produce a valid turn in "
            f"{max_attempts} attempts:\n" + "\n".join(rejections)
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
            reply = client.chat(messages, self.model, self.host, as_json=True,
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
            narration, repairs, repair_attempts = self._repair_outcome_claims(narration)
            attempts.extend(repair_attempts)
            return TurnPlan(narration=narration, intents=intents, attempts=attempts,
                            repairs=repairs, rejections=rejections)

        raise IntentError(
            f"the GM could not act for {ref} in {max_attempts} attempts:\n"
            + "\n".join(rejections)
        )

    # --- The prose itself ------------------------------------------------------------

    def _echo_index(self):
        if getattr(self, "_echoes", None) is None:
            self._echoes = narration_mod.build_echo_index(
                *[e["reply"]["narration"] for e in prompts.EXAMPLES],
                *[e["reply"]["narration"] for e in prompts.NPC_EXAMPLES],
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
        return {n for n in names if n}

    def polish(self, text: str, earlier: list[str] | None = None,
               min_chars: int = 0, player_input: str = "",
               scene_brief: str = "") -> tuple[str, list[str], list[Attempt]]:
        """One targeted rewrite when the prose breaks a rule about prose.

        Same shape as every fix that has held here: detect mechanically, then ask the
        model to repair only what was found. If the rewrite is no better the original is
        kept — blander prose is worth less than a lost turn.
        """
        review = narration_mod.review(
            text, pc_name=self._pc_name(), echo_index=self._echo_index(),
            known_names=self._known_names(), earlier=earlier, min_chars=min_chars,
        )
        if review.ok:
            return text, [], []

        try:
            reply = client.chat(
                prompts.narration_repair_messages(
                    text, review.complaint(), player_input, scene_brief),
                self.model, self.host, as_json=True, temperature=0.6, num_predict=900,
            )
            attempt = Attempt("polish", reply.seconds, reply.model, reply.text,
                              note="; ".join(review.as_log()))
            fixed = str(reply.json().get("narration", "")).strip()
        except Exception as exc:
            return text, [f"polish failed: {exc}"], [
                Attempt("polish", 0.0, self.model, note=str(exc)[:120])]

        after = narration_mod.review(
            fixed, pc_name=self._pc_name(), echo_index=self._echo_index(),
            known_names=self._known_names(), earlier=earlier, min_chars=min_chars,
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

        return " ".join(narration.split()), repairs, attempts

    # --- Call 2 -------------------------------------------------------------------------

    def narrate_outcome(self, narration: str, outcomes: list, player_input: str) -> tuple[str, Attempt]:
        """Say the facts the engine handed back.

        Fed only `player_visible()` outcomes, so a hidden roll's number is not in the
        context and cannot be leaked.
        """
        tells = [o.tell for o in outcomes if o.tell]
        because = [o.because for o in outcomes if o.because]
        if not tells:
            return "", Attempt("consequence", 0.0, self.model, note="nothing to narrate")

        reply = client.chat(
            prompts.call_two_messages(narration, tells, because, player_input),
            self.model, self.host, temperature=0.7, num_predict=250,
        )
        text = judgement.name_refs(reply.text.strip(), self.engine.scene)
        return text, Attempt("consequence", reply.seconds, reply.model, reply.text)


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
