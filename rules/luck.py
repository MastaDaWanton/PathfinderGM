"""Luck on a d20: the feats that reroll a roll or add to it after the die is down.

Feat loop b2-styles (2026-11-22). Each is a feat document's `luck` list (validated by
`classbuilder`), read here and nowhere else; the engine asks these functions at its two
d20 doors (`Engine._roll_or_suspend`, `_roll_or_suspend_stage`) and does the rolling. The
uses a day are a pool named for the feat (`resources.define`, refreshed by a night's rest),
so they show on the ability bar and refill through the one refresh path.

An entry is one of:

* `{"reroll": "natural_1" | "any", "rolls": [...], "per_day": 1}` — roll again and take
  the new die (Dauntless Destiny's natural 1; Close Call's "you must take the second
  roll, even if it's worse").
* `{"bonus": {"before": 8, "after": 4}, "rolls": ["d20"], "per_day": 1}` — Inexplicable
  Luck's "+8 ... before a roll is made ... after the roll is made ... +4".
* `{"ally_save": 30, "per_day": 1}` — Lucky Halfling: an ally within 30 ft who fails a
  save may take this creature's own roll of it.
* `{"on_reroll": 2, "bonus_type": "circumstance", "rolls": [...]}` — Strong Comeback's
  "+2 circumstance bonus on the reroll".
* `{"surge": 2, "bonus_type": "circumstance"}` — Surge of Success: a confirmed critical or
  a natural 20 on a save holds +2 for the next attack, save, skill or ability check
  "before the end of your next turn", as the effect `luck.surge`.

A roll's `kind` names what it is: `attack`, `save.fort`, `skill.disable device`,
`ability.str` — an entry's `rolls` are prefixes of it (`save` is every save, `d20` every
roll). Rerolls do not stack: "You may only make one reroll" (Dauntless Destiny), so a roll
is rerolled at most once whoever offers.

Prior art (searched 2026-11-22): Foundry PF1 leaves rerolls to the player's hand — a
chat-card button, no use count; Owlcat's Pathfinder CRPGs make them rule hooks on the d20
event (`RuleRollD20` with a reroll count), automatic for everybody. Here the player is
asked on their own die (the dice popup offers it) and everybody else is decided by the
book's trigger.
"""
from __future__ import annotations

from .dice import Modifier

SURGE = "luck.surge"
KINDS = ("reroll", "bonus", "ally_save", "on_reroll", "surge",
         # Feat loop b4-other (2026-11-26):
         # * `{"confirm_against": "lowest"}` — Deathless Zealot's "Whenever a creature rolls
         #   to confirm a critical hit against you, it must roll twice and take the lowest";
         # * `{"confirm_against": "reroll", "per_day": 1}` — Defiant Luck's "force the
         #   creature that confirmed the critical hit against you to reroll" (the bearer is
         #   the one struck; `Engine._confirm_against` asks);
         # * `{"twice": "higher", "rolls": ["skill.climb"]}` — Sure Grasp's "Roll twice ...
         #   and take the higher result" (`twice`, asked by the roll's own door).
         "confirm_against", "twice",
         # Feat loop b5-other (2026-11-26):
         # * `{"take_ten": true, "rolls": ["skill", "concentration"]}` — Perfect Center's
         #   "You can take 10 on any skill check or concentration check, even if it is not
         #   normally allowed": a before-the-roll offer to the player, and anybody else
         #   takes 10 when 10 makes it (`Engine._take_ten`), the swimmer's rule;
         # * `{"lend": "inexplicable-luck"}` — Bestow Luck's "use your Inexplicable Luck
         #   ability to grant an ally that can see and hear its benefit": the named
         #   feat's after-the-roll bonus, from its own uses, on an ally's d20 (`lenders`).
         # A `twice` entry with `spends` (Combat Meditation's "expend the +1 insight bonus
         # granted from the Meditation Master feat to instead roll twice") is a choice
         # made before the roll, paid from that feat's uses, never automatic.
         "take_ten", "lend")


def _entries(actor):
    """(feat document, entry) for every luck entry the creature's feats carry. An entry with
    `while` holds only while the bearer holds that tag (b4-other: Meditation Master's +1
    exists for the 24 hours after a meditation)."""
    from . import feats as feats_mod

    seen = set()
    for raw in getattr(actor, "feats", None) or ():
        doc = feats_mod.document(raw)
        if not doc or doc["id"] in seen:
            continue
        seen.add(doc["id"])
        for entry in doc.get("luck") or ():
            if entry.get("while") and not actor.has_state(str(entry["while"])):
                continue
            yield doc, entry


def confirm_against(actor, how: str) -> list:
    """(doc, entry) of the struck creature's luck on a roll to confirm against it, `how`
    "lowest" or "reroll", those with a use left."""
    return [(d, e) for d, e in _entries(actor)
            if e.get("confirm_against") == how and uses_left(actor, d, e)]


def twice(actor, kind: str, against=()):
    """The document whose `twice` entry covers this roll (Sure Grasp), or None."""
    for doc, entry in _entries(actor):
        if entry.get("twice") and not entry.get("spends") and covers(entry, kind, against):
            return doc
    return None


def paid_from(actor, entry: dict):
    """(doc, entry) of the feat whose uses a `spends` entry draws on, with one left — or
    (None, None). Combat Meditation spends Meditation Master's +1."""
    for d, e in _entries(actor):
        if d["id"] == entry.get("spends") and "bonus" in e and uses_left(actor, d, e):
            return d, e
    return None, None


def take_ten(actor, kind: str):
    """The document letting this creature take 10 on this roll, or None."""
    for doc, entry in _entries(actor):
        if entry.get("take_ten") and covers(entry, kind):
            return doc
    return None


def lenders(actor, scene) -> list:
    """(ally, lending doc, lent doc, lent entry) of the allies who may lend this creature
    a feat's after-the-roll bonus (Bestow Luck), each with a use of it left and seen by
    the creature it helps ("an ally that can see and hear")."""
    from . import awareness, reactions, states

    def party(c):
        return c.is_pc or c.has_state(states.TRAVELS_WITH_YOU)

    out = []
    for other in scene.actors.values():
        if other is actor or other.is_dead or other.is_down:
            continue
        if not (reactions._allied(scene, actor.ref, other.ref)
                or (party(actor) and party(other))):
            continue
        if not awareness.sees(scene, actor, other):
            continue
        for doc, entry in _entries(other):
            if not entry.get("lend"):
                continue
            lent, lent_entry = find(other, str(entry["lend"]), "bonus")
            if lent and (lent_entry["bonus"] or {}).get("after") \
                    and uses_left(other, lent, lent_entry):
                out.append((other, doc, lent, lent_entry))
    return out


def covers(entry: dict, kind: str, against=()) -> bool:
    """Whether an entry's `rolls` take in this roll (prefixes at a dot or space), and —
    when the entry names `against` — the roll is made against one of those (feat loop
    b3: Exile's Path's "a Will save against an enchantment spell or effect"; the words of
    `effectspec.AGAINST`, handed in by the save that rolls)."""
    if not kind:
        return False
    if entry.get("against") and not set(entry["against"]) & set(against or ()):
        return False
    # Feat loop b7-scoped: Dauntless Destiny's "This effect does not apply on saving
    # throws against traps or other objects".
    if set(entry.get("not_against") or ()) & set(against or ()):
        return False
    for want in entry.get("rolls") or ("d20",):
        want = str(want).lower()
        if want == "d20" or kind == want or kind.startswith(want + ".") \
                or kind.startswith(want + " "):
            return True
    return False


def pool_id(doc: dict) -> str:
    return str(doc["id"])


def uses_left(actor, doc: dict, entry: dict) -> int:
    """Uses left today, the pool defined on first ask (a feat's own uses a day)."""
    from . import resources

    per_day = int(entry.get("per_day") or 0)
    if per_day <= 0:
        return 1                                   # no limit written: always
    pool = resources.define(actor, {"id": pool_id(doc), "max": str(per_day),
                                    "refresh": "rest.night", "source": doc["name"]})
    return int(pool.current)


def spend(actor, doc: dict, entry: dict) -> bool:
    if int(entry.get("per_day") or 0) <= 0:
        return True
    if uses_left(actor, doc, entry) < 1:
        return False
    return bool(actor.spend_pool(pool_id(doc), 1).get("ok"))


def find(actor, feat_id: str, field: str):
    """The (doc, entry) of this feat whose entry carries `field`, or (None, None)."""
    for doc, entry in _entries(actor):
        if doc["id"] == feat_id and field in entry:
            return doc, entry
    return None, None


def before_offers(actor, kind: str) -> list[dict]:
    """What the player may take before the die is thrown (Inexplicable Luck's +8)."""
    out = []
    for doc, entry in _entries(actor):
        bonus = entry.get("bonus") or {}
        if bonus.get("before") and covers(entry, kind) and uses_left(actor, doc, entry):
            out.append({"id": doc["id"], "name": doc["name"], "when": "before",
                        "amount": int(bonus["before"]),
                        "text": f"+{int(bonus['before'])} on this roll ({doc['name']})"})
        # Feat loop b5-other: a roll made twice for another feat's use (Combat
        # Meditation), and taking 10 (Perfect Center).
        if entry.get("spends") and covers(entry, kind) and paid_from(actor, entry)[0]:
            paid = paid_from(actor, entry)[0]
            out.append({"id": doc["id"], "name": doc["name"], "when": "before",
                        "kind": "twice",
                        "text": f"Roll twice, keep the better ({doc['name']}, for "
                                f"{paid['name']})"})
        if entry.get("take_ten") and covers(entry, kind):
            out.append({"id": doc["id"], "name": doc["name"], "when": "before",
                        "kind": "take_ten", "text": f"Take 10 ({doc['name']})"})
    return out


def after_offers(actor, kind: str, roll, short: bool | None,
                 skip: str = "", against=()) -> list[dict]:
    """What may be done once the die is down: a reroll or a bonus. `short` is whether the
    total misses what it needed (None when that is not known — an opposed check); the
    offers that only matter on a miss are made only then, so the popup does not ask about
    every roll of the day."""
    out = []
    for doc, entry in _entries(actor):
        if doc["id"] == skip or not covers(entry, kind, against) \
                or not uses_left(actor, doc, entry):

            continue
        how = entry.get("reroll")
        if how == "natural_1" and roll.natural == 1:
            out.append({"id": doc["id"], "name": doc["name"], "kind": "reroll",
                        "text": f"Reroll the natural 1 ({doc['name']})"})
        elif how == "any" and short is not False:
            out.append({"id": doc["id"], "name": doc["name"], "kind": "reroll",
                        "text": f"Roll again and take the second die ({doc['name']})"})
        after = (entry.get("bonus") or {}).get("after")
        if after and short is not False:
            out.append({"id": doc["id"], "name": doc["name"], "kind": "bonus",
                        "amount": int(after),
                        "text": f"+{int(after)} after the roll ({doc['name']})"})
    return out


def comeback(actor, kind: str) -> list[Modifier]:
    """The bonus a reroll carries (Strong Comeback: ability checks, skills and saves)."""
    out = []
    for doc, entry in _entries(actor):
        n = int(entry.get("on_reroll") or 0)
        if n and covers(entry, kind):
            out.append(Modifier(n, doc["name"], str(entry.get("bonus_type") or "")))
    return out


def surge_terms(actor, kind: str) -> list[Modifier]:
    """The held Surge of Success, on the next attack, save, skill or ability check."""
    if not kind.split(".")[0] in ("attack", "save", "skill", "ability"):
        return []
    held = [e for e in getattr(actor, "effects", None) or ()
            if any(str(t) == SURGE for t in e.tags or ())]
    if not held:
        return []
    e = held[0]
    return [Modifier(int((e.payload or {}).get("amount") or 2), e.source,
                     str((e.payload or {}).get("bonus_type") or "circumstance"))]


def surge_effect(actor):
    """Surge of Success's held bonus, or None when the creature has no such feat."""
    from .activeeffect import ActiveEffect

    for doc, entry in _entries(actor):
        n = int(entry.get("surge") or 0)
        if n:
            # "before the end of your next turn": this turn and the next, on the round
            # ticker (two ticks).
            return ActiveEffect(
                name=doc["name"].lower(), kind="buff", key=doc["id"], source=doc["name"],
                origin=f"rule:feat-{doc['id']}", duration="rounds", rounds_left=2,
                tags=(SURGE,),
                payload={"amount": n, "bonus_type": entry.get("bonus_type") or ""})
    return None


def ally_savers(actor, scene, gap_ft) -> list:
    """(creature, doc, entry) of the allies who may lend this creature their save
    (Lucky Halfling, "one of your allies within 30 feet"), nearest first."""
    from . import reactions, states

    def party(c):
        return c.is_pc or c.has_state(states.TRAVELS_WITH_YOU)

    out = []
    for other in scene.actors.values():
        if other is actor or other.is_dead or other.is_down:
            continue
        # A side in a fight; out of one, the player and those who travel with them.
        if not (reactions._allied(scene, actor.ref, other.ref)
                or (party(actor) and party(other))):
            continue
        for doc, entry in _entries(other):
            reach = int(entry.get("ally_save") or 0)
            if not reach or not uses_left(other, doc, entry):
                continue
            far = gap_ft(other, actor)
            if far is not None and far > reach:
                continue
            out.append((far if far is not None else 0, other, doc, entry))
    return [(o, d, e) for _, o, d, e in sorted(out, key=lambda x: x[0])]
