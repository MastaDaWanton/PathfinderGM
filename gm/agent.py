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

from . import client, prompts


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

    # --- Call 1 ---------------------------------------------------------------------

    def plan_turn(
        self, player_input: str, history: list[dict], location=None,
        recent_events=None, max_attempts: int = 5,
    ) -> TurnPlan:
        """
        Five attempts, not three. Measured across live turns: the model makes a
        *different* mistake each time rather than repeating one, so each rejection
        genuinely teaches it something and three was cutting it off mid-convergence. A
        warm attempt costs about 4s, so five is a worst case of ~20s — cheap against
        losing the turn.
        """
        brief = prompts.scene_brief(self.world, self.engine.scene, location, recent_events)
        messages = prompts.call_one_messages(brief, history, player_input)

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
                messages = _with_correction(messages, reply.text, str(exc))
                continue

            narration = str(data.get("narration", "")).strip()
            try:
                # Checks 1, 2 and 3. A malformed intent has no repairable content, so
                # these are hard rejections that regenerate — but the rejection text
                # names the legal refs and vocabularies, which turns a blind retry into
                # a repair.
                intents = self.engine.validate(data.get("intents"))
            except IntentError as exc:
                rejections.append(f"attempt {n + 1} [{exc.check}]: {exc}")
                messages = _with_correction(messages, reply.text, str(exc))
                continue

            # Check 4 is the only one that gets a targeted repair, because the narration
            # around the claim is worth keeping.
            narration, repairs, repair_attempts = self._repair_outcome_claims(narration)
            attempts.extend(repair_attempts)

            return TurnPlan(narration=narration, intents=intents, attempts=attempts,
                            repairs=repairs, rejections=rejections)

        raise IntentError(
            "the GM could not produce a valid turn in "
            f"{max_attempts} attempts:\n" + "\n".join(rejections)
        )

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
        text = reply.text.strip()
        return text, Attempt("consequence", reply.seconds, reply.model, reply.text)


def _with_correction(messages: list[dict], bad_reply: str, problem: str) -> list[dict]:
    """Feed the rejection back so the retry is a repair rather than a fresh guess."""
    return messages + [
        {"role": "assistant", "content": bad_reply},
        {"role": "user", "content":
            f"That was rejected by the rules engine: {problem}\n"
            f"Send the same turn again, corrected."},
    ]
