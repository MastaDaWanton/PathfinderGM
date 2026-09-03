"""The one record for everything that changes a number and later stops.

Stage 2 of docs/states-effects-tells.md. The sheet grew five separately maintained
mechanisms — conditions, buffs, temporary hit point pools, weapon coatings, and the
ability bonuses nothing ever applied — each with its own add, its own expiry, and its
own corner of `tick_conditions`. Every one was a copy of the same idea: *something is
on this creature, it changes numbers or grants states while it holds, and it must be
possible to remove it and have its contribution evaporate.*

`ActiveEffect` is that idea said once. A condition is an effect whose granted tags are
its `rules/states.py` entry; a buff is an effect carrying one modifier; a pool of
temporary hit points is an effect with an amount that damage spends; a coating is an
effect holding a payload the next hit delivers. The applicator and the ticker live on
the Actor (`apply_effect`, `tick_effects`) because they read and write actor state;
this module owns the record and its serialisation so the two cannot drift.

Nothing here is ever "added and hopefully subtracted": remove the effect and every
modifier, tag and pool it carried goes with it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Duration kinds. "instant" never lands on the list — an instant effect is applied and
# done — but the vocabulary names it so a document can say it and a validator can check.
DURATIONS = ("instant", "rounds", "until-dismissed")

# Stacking policies the applicator understands.
#   refresh   — the same effect reapplied resets its clock and values; never two copies.
#   stack     — copies from different applications accumulate (a Coagulator's pools).
STACKINGS = ("refresh", "stack")


@dataclass
class ActiveEffect:
    """One thing that is on a creature and will later stop being on it."""

    name: str = ""                    # what the sheet and the tell call it
    kind: str = "effect"              # condition | buff | temp_hp | coating | ability
    key: str = ""                     # the condition key, for conditions
    source: str = ""                  # what put it here — the label the popup shows
    # The document reference behind `source` (`item:<id>`, `spell:<id>`, ...), when a
    # door stamped one. Foundry's word: the field it freed for "who applied this from
    # outside" once effects stopped being copied off items. Not a dependency the
    # applicator checks — a potion's last dose has no stock row by the time its heal
    # lands — but what a test can ask "was this stamped by a door" of.
    origin: str = ""
    duration: str = "until-dismissed"
    rounds_left: int | None = None    # None = until dismissed
    # Granted tags: the vocabulary entry for a condition, a stance's own tag for an
    # ability. `Actor.has_state` reads these — every effect participates, not only
    # conditions, which is what lets a stance answer "buff.stance" without being one.
    tags: tuple[str, ...] = ()
    # Source-tracked modifiers: {"kind": "save_mod", "target": "will", "amount": 1,
    # "bonus_type": "alchemical", "note": ...}. They flow through the existing
    # modifier lists (`Actor._buff_mods`) so the dice popup keeps naming every number.
    modifiers: list[dict] = field(default_factory=list)
    # A pool the effect carries: temporary hit points spent by damage.
    amount: int = 0
    # Anything the mechanisms above cannot hold: a coating's dose, a granted weapon.
    payload: dict = field(default_factory=dict)
    stacking: str = "refresh"
    # Per-round work: effect specs run by the ticker each round while this holds.
    periodic: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "kind": self.kind, "key": self.key,
            "source": self.source, "origin": self.origin, "duration": self.duration,
            "rounds_left": self.rounds_left, "tags": list(self.tags),
            "modifiers": [dict(m) for m in self.modifiers],
            "amount": self.amount, "payload": dict(self.payload),
            "stacking": self.stacking,
            "periodic": [dict(p) for p in self.periodic],
        }

    @property
    def ended_label(self) -> str:
        """The line `tick_effects` reports when this expires.

        These are the exact strings the pre-unification tickers produced, kept because
        tests and play transcripts read them: a pool ends as "blood sponge (5 temp)",
        a buff as "Acacia tea (+1 will)".
        """
        if self.kind == "temp_hp":
            return f"{self.source or 'temporary hit points'} ({self.amount} temp)"
        if self.kind == "buff" and self.modifiers:
            m = self.modifiers[0]
            return (f"{self.source or 'a preparation'} "
                    f"({int(m.get('amount', 0)):+d} {m.get('target', '')})")
        return self.name or self.source or "an effect"


def _tags_on_load(d: dict) -> tuple[str, ...]:
    """The stored tags, plus whatever the vocabulary says the key grants today.

    A save is a record of what happened, not a second copy of the vocabulary. Tags were
    frozen at write time, so a condition saved before its entry gained a family kept the
    old answer for the life of the campaign — a `helpless` prisoner saved yesterday
    would still not be `state.unable` after the vocabulary said it was, and no test
    anywhere would notice, because every test builds its actors fresh.

    Unioned rather than replaced: `_apply_ability_document` appends a document's own
    declared tags on top of `tags_for`, and rebuilding from the key alone would delete
    them on the next load.
    """
    stored = tuple(str(t) for t in (d.get("tags") or ()))
    key = str(d.get("key", "") or "")
    if str(d.get("kind", "") or "") != "condition" or not key:
        return stored
    from .states import tags_for

    # Added to, not replaced. Rebuilding the namespaces the vocabulary owns is the only
    # way to RETIRE an answer, and it was tried — but `_apply_ability_document` appends
    # a document's own tags in *any* namespace, so it deleted them: measured, an ability
    # granting `state.unable.trance` blocked actions in session and stopped blocking
    # after a restart, and a homebrew condition declaring `recovery.rest` was cleared by
    # a night's sleep until the campaign was reloaded. Destroying a document's tags is
    # worse than carrying a stale one.
    #
    # The cost of the union, stated rather than hidden: a tag this file WITHDRAWS never
    # reaches a condition already on disk, and is written back on the next save. Nothing
    # has needed to withdraw one yet. Doing it safely needs documents to record their
    # own tags separately from the vocabulary's, which is a save-shape change.
    return stored + tuple(t for t in tags_for(key) if t not in stored)


def from_dict(d: dict) -> ActiveEffect:
    return ActiveEffect(
        name=str(d.get("name", "") or ""),
        kind=str(d.get("kind", "effect") or "effect"),
        key=str(d.get("key", "") or ""),
        source=str(d.get("source", "") or ""),
        # "" for every effect saved before stage 8: the law is about what arrives.
        origin=str(d.get("origin", "") or ""),
        duration=str(d.get("duration", "until-dismissed") or "until-dismissed"),
        rounds_left=d.get("rounds_left"),
        tags=_tags_on_load(d),
        modifiers=[dict(m) for m in (d.get("modifiers") or [])],
        amount=int(d.get("amount", 0) or 0),
        payload=dict(d.get("payload") or {}),
        stacking=str(d.get("stacking", "refresh") or "refresh"),
        periodic=[dict(p) for p in (d.get("periodic") or [])],
    )
