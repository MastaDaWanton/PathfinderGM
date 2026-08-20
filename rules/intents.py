"""Intents: what the GM agent is allowed to say, and how we check that it said it.

The wire format is docs/intent-protocol.md. This module is the validating half — the four
mechanical checks that run on every GM emission before anything is resolved:

  1. schema      — is this a shape we recognise?
  2. refs        — does every actor and target exist in the engine's registry?
  3. legality    — can that actor actually do that right now?
  4. outcome     — did the narration state a mechanical result it does not get to state?

None of these is an instruction in a prompt. That is the point. Every quality fix that
held in World Bible detected the defect in code and then asked the model to repair only
what was found; every fix that relied on instructing the model to behave differently
failed and kept failing.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .tables import CIRCUMSTANCE, DC_BANDS, SAVES, SKILLS, WEAPONS

# Skill names from other editions, mapped to the 1e name they unambiguously mean.
#
# Measured, not guessed: on the first live turn against llama3.1:8b the model emitted
# "melee", "initiative" and "dodge" as skills on three consecutive attempts and lost the
# turn. A model has read far more 5e and 3.5e than Pathfinder 1e, so it reaches for those
# vocabularies under pressure. Mapping the unambiguous ones costs nothing and removes a
# whole class of lost turn; the ambiguous ones (athletics is climb *or* swim) are left to
# be rejected with a suggestion, because guessing between them would be inventing a
# mechanic.
SKILL_ALIASES: dict[str, str] = {
    "sneak": "stealth", "sneaking": "stealth", "hide": "stealth", "hiding": "stealth",
    "notice": "perception", "spot": "perception", "listen": "perception",
    "search": "perception", "investigation": "perception", "awareness": "perception",
    "insight": "sense motive", "empathy": "sense motive",
    "persuasion": "diplomacy", "deception": "bluff", "lying": "bluff",
    "athletics (climb)": "climb", "athletics (swim)": "swim",
    "tumbling": "acrobatics", "balance": "acrobatics", "jump": "acrobatics",
    "open lock": "disable device", "open locks": "disable device",
    "lockpicking": "disable device", "thievery": "disable device",
    "pick pocket": "sleight of hand", "arcana": "knowledge (arcana)",
    "history": "knowledge (history)", "nature": "knowledge (nature)",
    "religion": "knowledge (religion)", "streetwise": "knowledge (local)",
    "medicine": "heal", "animal handling": "handle animal",
}


def normalise_skill(name: str) -> str | None:
    """The 1e skill this name means, or None if it means nothing we have."""
    key = str(name).strip().lower()
    if key in SKILLS:
        return key
    return SKILL_ALIASES.get(key)


_DC_NUMBER_RE = re.compile(r"^\s*(?:dc\s*)?(-?\d+)\s*$", re.IGNORECASE)


def normalise_dc(spec, op: str, index: int) -> dict:
    """Canonicalise every shape a DC can arrive in, and reject the rest.

    Validation has to cover everything resolution accepts, or the gap between them
    becomes an uncaught crash instead of a rejection the model could repair. That is
    exactly what happened on the second live turn: `rules.dc.resolve` accepted a bare
    string, `_check_params` only validated the dict form, and the model's perfectly
    reasonable `"dc": "DC 15"` sailed past check 1 and 500'd inside the engine.

    "DC 15" is now read as the value 15 — it is a natural thing to write, and a stated
    value is already a supported (clamped) input.
    """
    if isinstance(spec, bool):
        raise IntentError(f"{op}: dc must be a difficulty band or a number", "schema", index)
    if isinstance(spec, (int, float)):
        return {"value": int(spec)}
    if isinstance(spec, str):
        m = _DC_NUMBER_RE.match(spec)
        if m:
            return {"value": int(m.group(1))}
        spec = {"band": spec}
    if not isinstance(spec, dict):
        raise IntentError(
            f"{op}: dc must be a difficulty band or a number, got {spec!r}", "schema", index
        )

    if spec.get("value") is not None and not spec.get("band"):
        try:
            return {"value": int(spec["value"])}
        except (TypeError, ValueError):
            raise IntentError(
                f"{op}: dc value {spec['value']!r} is not a number", "schema", index
            )

    band = str(spec.get("band", "")).strip().lower().replace(" ", "_")
    if band in DC_BANDS:
        return {"band": band}
    m = _DC_NUMBER_RE.match(band.replace("_", " "))
    if m:
        return {"value": int(m.group(1))}
    raise IntentError(
        f"{op}: {spec.get('band')!r} is not a difficulty band."
        + _suggest(band, DC_BANDS)
        + f" The bands are: {', '.join(DC_BANDS)}. A plain number is also accepted.",
        "schema", index,
    )


def _suggest(name: str, candidates) -> str:
    """A rejection the model cannot act on costs a whole regeneration.

    Naming the nearest legal value turns a blind retry into a repair, which is the same
    reason the ref rejection lists the refs that do exist.
    """
    close = difflib.get_close_matches(str(name).strip().lower(), list(candidates), n=3, cutoff=0.5)
    if close:
        return " Did you mean " + " or ".join(repr(c) for c in close) + "?"
    return ""

# --- The op table ------------------------------------------------------------------

# op -> (required params, optional params, default visibility)
OPS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str]] = {
    "check": (("skill",), ("dc", "opposed_by", "circumstance", "aid"), "player"),
    "save": (("save", "dc"), ("on_success", "on_failure"), "player"),
    # `player`, because the PC rolls their own to-hit and their own damage. Defaulting
    # this to `hidden` meant the engine silently rolled the player's attacks for them,
    # which contradicts the architecture decision outright. NPC attacks still resolve
    # hidden — `Engine._force_visibility` demotes any non-PC actor.
    "attack": ((), ("weapon", "full_attack", "manoeuvre", "power_attack"), "player"),
    "damage": (("amount", "type"), ("to",), "hidden"),
    "condition": (("condition",), ("duration", "to"), "hidden"),
    "begin_encounter": (("sides",), ("surprise",), "hidden"),
    "move": (("zone",), ("who",), "hidden"),
    "spawn": (("template",), ("from_entity_id", "count", "name"), "hidden"),
    "advance_time": (("amount", "unit"), (), "hidden"),
    "narrate_only": ((), (), "hidden"),
}

VISIBILITIES = ("player", "hidden")

# Params the GM keeps supplying that the *engine* owns. docs/intent-protocol.md §1 is
# explicit about these: "the engine ignores it and logs the discrepancy... a turn that
# dies because the model said '+7' is worse than one that overrides it." Hard-rejecting
# them contradicted that rule, and in live play it killed five consecutive attack
# attempts over `damage_type`, `dice` and `damage_roll` — all of which the engine reads
# off the weapon anyway.
#
# A param that is merely *unrecognised* is still rejected. The difference matters: an
# ignored engine-owned param is a value we can already compute, while an unknown one is
# a mechanic the GM believes it applied and we have never heard of.
ENGINE_OWNED_PARAMS = {
    "damage", "damage_type", "damage_roll", "damage_dice", "dice", "die",
    "attack_bonus", "attack_roll", "to_hit", "bonus", "modifier", "modifiers",
    "ac", "target_ac", "hit", "crit", "critical", "result", "outcome", "total",
    "skill", "roll", "dc_value", "save_bonus", "initiative",
}

# The model keeps reaching for a third word meaning "the engine rolls this one, not the
# player" — observed as "gm" and "game" on separate live turns. That is exactly what
# `hidden` means, so it is mapped rather than rejected.
VISIBILITY_ALIASES = {
    "gm": "hidden", "game": "hidden", "engine": "hidden", "dm": "hidden",
    "secret": "hidden", "gm_only": "hidden", "behind_the_screen": "hidden",
    "npc": "hidden", "none": "hidden",
    "pc": "player", "player_visible": "player", "open": "player", "public": "player",
    "visible": "player",
}
ZONES = ("engaged", "near", "far")
TIME_UNITS = ("round", "minute", "hour", "day")


class IntentError(ValueError):
    """A malformed or illegal intent. Carries which check rejected it, so the caller can
    decide between a regenerate and a targeted repair."""

    def __init__(self, message: str, check: str = "schema", index: int | None = None):
        super().__init__(message)
        self.check = check
        self.index = index


@dataclass
class Intent:
    op: str
    actor: str | None = None
    target: str | list[str] | None = None
    because: str = ""
    params: dict = field(default_factory=dict)
    visibility: str = ""
    id: str = ""
    # Engine-owned params the GM supplied and we dropped. Not an error, but the log is
    # the early warning that a prompt has drifted.
    ignored_params: list[str] = field(default_factory=list)

    def targets(self) -> list[str]:
        if self.target is None:
            return []
        return list(self.target) if isinstance(self.target, list) else [self.target]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "op": self.op, "actor": self.actor, "target": self.target,
            "because": self.because, "params": self.params, "visibility": self.visibility,
            "ignored_params": self.ignored_params,
        }


# --- Check 1: schema ------------------------------------------------------------------

def parse(raw: dict, index: int = 0) -> Intent:
    if not isinstance(raw, dict):
        raise IntentError(f"intent {index} is not an object", "schema", index)

    op = str(raw.get("op", "")).strip().lower()
    if op not in OPS:
        raise IntentError(
            f"unknown op {op!r}; expected one of {sorted(OPS)}", "schema", index
        )

    required, optional, default_vis = OPS[op]
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        raise IntentError(f"{op}: params must be an object", "schema", index)

    missing = [p for p in required if params.get(p) in (None, "")]
    if missing:
        raise IntentError(
            f"{op}: missing required param(s) {', '.join(missing)}", "schema", index
        )

    unknown = set(params) - set(required) - set(optional)
    ignored = sorted(unknown & ENGINE_OWNED_PARAMS)
    for key in ignored:
        params.pop(key, None)
    unknown -= set(ignored)
    if unknown:
        raise IntentError(
            f"{op}: unknown param(s) {', '.join(sorted(unknown))}. "
            f"{op} takes {', '.join(sorted(set(required) | set(optional))) or 'no params'}.",
            "schema", index,
        )

    visibility = str(raw.get("visibility") or default_vis).strip().lower()
    visibility = VISIBILITY_ALIASES.get(visibility, visibility)
    if visibility not in VISIBILITIES:
        raise IntentError(
            f"{op}: visibility is {VISIBILITIES[0]!r} (the player rolls it) or "
            f"{VISIBILITIES[1]!r} (the engine rolls it), got {visibility!r}",
            "schema", index,
        )

    intent = Intent(
        op=op,
        actor=raw.get("actor"),
        target=raw.get("target"),
        because=str(raw.get("because") or "").strip(),
        params=params,
        visibility=visibility,
        id=str(raw.get("id") or f"i{index + 1}"),
        ignored_params=ignored,
    )
    _check_params(intent, index)
    return intent


def _check_params(intent: Intent, index: int) -> None:
    """Per-op value checks. Closed vocabularies are checked here rather than trusted,
    because a closed vocabulary the code does not enforce is just a suggestion."""
    p, op = intent.params, intent.op

    if op == "check":
        raw_skill = str(p["skill"]).strip().lower()
        # Attacking is not a skill check in 1e, and the model reaches for one. Say so,
        # rather than making it guess from a list that will never contain the answer.
        if raw_skill in ("attack", "melee", "melee attack", "ranged attack", "to hit",
                         "weapon", "combat", "strike", "hit"):
            raise IntentError(
                f"check: attacking is not a skill check. Use "
                '{"op": "attack", "actor": "...", "target": "..."} — the engine works '
                "out the attack bonus, the target's AC and the damage from the sheets.",
                "schema", index,
            )
        if raw_skill in ("initiative", "init", "reflexes"):
            raise IntentError(
                "check: initiative is not a skill check. Use "
                '{"op": "begin_encounter", "params": {"sides": {"pc": ["pc"], '
                '"them": ["<ref>"]}}} — the engine rolls initiative for everyone.',
                "schema", index,
            )
        skill = normalise_skill(raw_skill)
        if skill is None:
            raise IntentError(
                f"check: {raw_skill!r} is not a Pathfinder 1e skill."
                + _suggest(raw_skill, SKILLS)
                + f" The skills are: {', '.join(sorted(SKILLS))}.",
                "schema", index,
            )
        p["skill"] = skill
        if p.get("opposed_by"):
            ob = p["opposed_by"]
            if not isinstance(ob, dict) or "ref" not in ob or "skill" not in ob:
                raise IntentError(
                    "check: opposed_by needs {ref, skill}", "schema", index
                )
            raw_os = str(ob["skill"]).strip().lower()
            os_ = normalise_skill(raw_os)
            if os_ is None:
                raise IntentError(
                    f"check: {raw_os!r} is not a Pathfinder 1e skill and cannot oppose "
                    f"a check." + _suggest(raw_os, SKILLS)
                    + " To have someone resist by noticing, oppose with 'perception'.",
                    "schema", index,
                )
            ob["skill"] = os_
        if not p.get("dc") and not p.get("opposed_by"):
            raise IntentError(
                "check: a check needs something to beat. Add either "
                '"dc": {"band": "tough"} (one of ' + ", ".join(DC_BANDS) + "), or "
                '"opposed_by": {"ref": "<a ref in the scene>", "skill": "perception"} '
                "when someone is actively resisting.",
                "schema", index,
            )

    elif op == "save":
        save = str(p["save"]).strip().lower()
        aliases = {"fortitude": "fort", "reflex": "ref"}
        save = aliases.get(save, save)
        if save not in SAVES:
            raise IntentError(f"save: no such save {save!r}", "schema", index)
        p["save"] = save

    elif op == "attack":
        w = p.get("weapon")
        if w and str(w).strip().lower() not in WEAPONS:
            raise IntentError(f"attack: no such weapon {w!r}", "schema", index)
        if w:
            p["weapon"] = str(w).strip().lower()
        p["full_attack"] = bool(p.get("full_attack", False))

    elif op == "move":
        zone = str(p["zone"]).strip().lower()
        if zone not in ZONES:
            raise IntentError(
                f"move: zone must be one of {ZONES}, got {zone!r}", "schema", index
            )
        p["zone"] = zone

    elif op == "advance_time":
        unit = str(p["unit"]).strip().lower().rstrip("s")
        if unit not in TIME_UNITS:
            raise IntentError(
                f"advance_time: unit must be one of {TIME_UNITS}, got {unit!r}",
                "schema", index,
            )
        p["unit"] = unit
        try:
            p["amount"] = int(p["amount"])
        except (TypeError, ValueError):
            raise IntentError("advance_time: amount must be a number", "schema", index)

    elif op == "begin_encounter":
        if not isinstance(p["sides"], dict):
            raise IntentError(
                "begin_encounter: sides must be an object of side -> [refs]",
                "schema", index,
            )

    # The DC spec, wherever it appears, is canonicalised here so that resolution only
    # ever sees a shape it fully understands.
    if p.get("dc") is not None:
        p["dc"] = normalise_dc(p["dc"], op, index)

    circ = p.get("circumstance")
    if circ:
        if isinstance(circ, str):
            circ = {"value": circ}
            p["circumstance"] = circ
        val = str(circ.get("value", "")).strip().lower()
        if val not in CIRCUMSTANCE:
            raise IntentError(
                f"{op}: circumstance must be one of {sorted(CIRCUMSTANCE)}, got "
                f"{val!r}", "schema", index,
            )
        circ["value"] = val


def parse_all(raw_intents: list) -> list[Intent]:
    if not isinstance(raw_intents, list):
        raise IntentError("intents must be a list", "schema")
    if not raw_intents:
        # Absence is never silently acceptable. `narrate_only` exists precisely so that
        # "nothing mechanical happened" is a thing the GM says out loud, which makes a
        # model that forgot to emit intents a detectable failure rather than an
        # invisible one.
        raise IntentError(
            "no intents emitted; a turn with no mechanics must say so with "
            "narrate_only", "schema",
        )
    return [parse(r, i) for i, r in enumerate(raw_intents)]


# --- Check 4: the outcome-claim detector ------------------------------------------------

# Phrasings that assert a mechanical result. Every one of these is something a model
# actually produced in testing while being asked, in the prompt, not to.
_OUTCOME_PATTERNS: list[tuple[str, str]] = [
    (r"\byou (?:take|suffer|lose)\b[^.]{0,30}?\b\d+\b", "states damage taken"),
    (r"\b\d+\s*(?:points? of\s*)?damage\b", "states a damage number"),
    (r"\byour?\s+(?:hit points?|hp)\b", "states hit points"),
    (r"\byou (?:succeed|fail|manage to|barely make|don't make)\b", "states success or failure"),
    (r"\byou(?:'re| are) (?:hit|struck|wounded|killed|dead)\b", "states being hit"),
    (r"\b(?:the (?:blow|blade|arrow|bolt|strike)|it) (?:lands|connects|bites|sinks|finds)\b",
     "states an attack landing"),
    (r"\b(?:misses|missed|goes wide|glances off|skitters past)\b", "states an attack missing"),
    (r"\byou (?:dodge|duck|roll) (?:clear|aside|away)\b", "states a save succeeding"),
    (r"\bthe (?:save|check|roll) (?:succeeds|fails)\b", "states a roll's result"),
    (r"\byou slip (?:past|by) (?:him|her|them|the guard)\b", "states a stealth result"),
    (r"\bunnoticed\b|\bwithout being (?:seen|heard|noticed)\b", "states a stealth result"),
    # "…goes back to his cup, unaware." — produced in live play, in the *setup*
    # narration, before the opposed Stealth check had been rolled. The GM had decided
    # the guildhand failed his Perception. Caught only by playing, which is why the rule
    # is to verify on real regenerated content and not on the phrasings you imagined.
    (r"\bunaware\b|\boblivious\b|\bnone the wiser\b", "states a perception result"),
    (r"\b(?:doesn't|does not|didn't|did not|never) (?:see|hear|notice|spot|catch)\b",
     "states a perception result"),
    (r"\bnever (?:sees|hears|notices|spots)\b", "states a perception result"),
    (r"\bfails? to (?:see|hear|notice|spot)\b", "states a perception result"),
    (r"\bdc\s*\d+", "states a DC in prose; the DC belongs in the intent"),
    (r"\broll(?:s|ed)? a\s*\d+", "states a die result"),
    (r"\bnatural (?:20|one|1)\b", "states a die result"),
]

OUTCOME_RE = [(re.compile(p, re.IGNORECASE), why) for p, why in _OUTCOME_PATTERNS]


@dataclass
class OutcomeClaim:
    pattern: str
    why: str
    text: str
    start: int
    end: int

    @property
    def sentence(self) -> str:
        return self.text


def find_outcome_claims(narration: str) -> list[OutcomeClaim]:
    """Every place the narration asserts a mechanical result.

    This is what makes the architecture's central promise true. "A persuasive model
    narrating a hit that actually missed" is not prevented by asking the model not to; it
    is prevented by looking, in code, every single turn.
    """
    claims: list[OutcomeClaim] = []
    for rx, why in OUTCOME_RE:
        for m in rx.finditer(narration or ""):
            claims.append(
                OutcomeClaim(
                    pattern=rx.pattern, why=why, text=_sentence_around(narration, m.start()),
                    start=m.start(), end=m.end(),
                )
            )
    return claims


def _sentence_around(text: str, index: int) -> str:
    start = max(
        (text.rfind(c, 0, index) for c in ".!?\n"), default=-1
    )
    end_candidates = [text.find(c, index) for c in ".!?\n"]
    end_candidates = [e for e in end_candidates if e != -1]
    end = min(end_candidates) + 1 if end_candidates else len(text)
    return text[start + 1:end].strip()
