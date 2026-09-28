"""Prose that says what a hand holds, or what a body suffers, against the state.

Measured 2026-09-27 in a live scripted fight (gemma-4-12B through /api/say, recorded in
docs/maneuver-outcomes.md "Live runs"). The engine's state matched every tell, and the
prose written after the dice — `narrate_turn`, the one door the player reads — did not:

  1. "Kesst Vayr drops the rapier" (the player's own failed disarm) became "The rapier
     clatters against the floorboards, sliding a few feet away as his grip fails" — the
     ENEMY's grip;
  2. "driven against something solid and goes nowhere" left him "momentarily stunned"
     and "sprawling", with neither on the books;
  3. "Kesst Vayr's steal fails ... by 16" sent "the purse tumbling from his hip; it hits
     the floor" — the purse still on his belt, nine silver in it;
  4. an unarmed strike, the rapier on the props ledger, was "Your blade whistles";
  5. a failed overrun had "Your rapier slips from your grip", two turns after it fell.

The claim scrubber (`rules.intents.find_outcome_claims`) reads mechanics off the words
alone and asks whether the outcomes back that KIND of claim; nothing asked the state
WHO holds WHAT, or whether a body carries the condition it is said to. These three
questions do, by set comparison against the facts: `Actor.equipped` and the weapon it
resolves to, the turn's effect records (`dropped`, `stolen`, `picked_up`, `condition`),
and `has_state` on the condition's tag. They find; `GMAgent._repair_state_claims`
rewrites the one sentence with the fact named, and cuts it when the rewrite still says
it (the detect-then-targeted-repair shape every fix that held in this project has had).

Deliberately narrow, because a false positive cuts a true sentence from the only prose
the player reads:

  * a dead or downed body's weapon falling is let be — the engine keeps a corpse's sap
    `equipped`, and "his club clatters to the floor as he falls" is the commonest good
    death sentence there is;
  * conditions only in their physical sense: "stunned silence" and "a stunned look" are
    faces, not the condition;
  * hedged and denied claims ("nearly tears the blade from his hand", "does not fall")
    are not claims;
  * the player's weapon is judged only in the second person, after the name swap, and a
    creature's only when no creature here holds anything.
"""
from __future__ import annotations

import re

# Things a hand holds that the engine keeps a record of. Generic nouns, because the
# model says "blade" and "steel" for a rapier; the real names of what is carried here
# join them per scene.
_WEAPON_WORDS = ("blade", "steel", "sword", "rapier", "dagger", "knife", "axe", "mace",
                 "club", "spear", "sap", "hammer", "cudgel", "scimitar", "sabre", "saber",
                 "falchion", "longsword", "shortsword", "greatsword", "flail", "maul",
                 "whip", "weapon", "crossbow", "bow", "halberd", "glaive", "staff")
_PURSE_WORDS = ("purse", "pouch", "coin purse", "coins")
_SHIELD_WORDS = ("shield", "buckler")

# A thing leaving a hand, in the two shapes English has for it. The thing as SUBJECT —
# "the purse tumbling from his hip", "your rapier slips from your grip": the verb comes
# after it. The thing as OBJECT — "drops his sword", "knocks the blade from his hand":
# the verb comes before it, and a verb that is not about the thing does not count
# ("your fingers slip against the slick, heavy pouch" is the fingers slipping — flagged
# by the first draft of this, which let any leaving verb before the thing count).
# Each needs a way OUT of the hand or a floor to land on: "the hammer falls" is a blow,
# "clattering against the heavy timber of the wall" a miss (replayed on the recorded
# corpus, 2026-09-27, the bare verbs flagged a smith's hammer).
_OUT = (r"(?:from|out\s+of|off|free|loose|away|to\s+the|onto\s+the|across\s+the|into\s+the|"
        r"against\s+the|on\s+the|in\s+the)\s*(?:\w+\s+){0,2}?")
_FLOOR = r"(?:floor|floorboards|boards|ground|dirt|mud|sawdust|stones|cobbles|cobblestones|deck|flagstones|straw|rushes|planks)"
_LEAVES_AFTER = (r"(?:(?:drops?|dropped|clatter(?:s|ed|ing)?|tumbl(?:es|ed|ing)|"
                 r"skitter(?:s|ed|ing)?|slid(?:e|es|ing)|falls?|fell|falling|lands?|landing)"
                 rf"\s+(?:\w+\s+){{0,2}}?(?:{_OUT}{_FLOOR}|(?:from|out\s+of)\s+(?:his|her|their|its|your)\b)"
                 r"|(?:slips?|slipped|slipping|tumbl(?:es|ed|ing)|flies|flew|flying|torn|wrenched|ripped|"
                 r"knocked|jerked)\s+(?:\w+\s+){0,2}?(?:from|out\s+of|free|loose)\b"
                 r"|spins?\s+away|spinning\s+away|goes\s+flying|sent\s+(?:flying|spinning|skittering))")
# A verb that alone says the thing left a hand: "drops his sword", "lets go of the club".
_LEAVES_BEFORE = (r"(?:drops?|dropped|dropping|lets?\s+go\s+of|"
                  r"los(?:es|t|ing)\s+(?:his|her|their|its|your)\s+grip\s+on)")
# A verb that says so only with its particle AFTER the thing: "knocks the blade FROM his
# hand", "wrenches the sword FREE"; "knocks the table" is nothing.
_FORCES_BEFORE = (r"(?:knock|tear|tore|torn|wrench|rip|pry|pries|prise|twist|strike|"
                  r"struck|slap|send|sent|flick|jerk|yank)\w*")
_PARTICLE_AFTER = (r"^[^.!?;]{0,30}?\b(?:from|out\s+of|loose|free|away|flying|spinning|"
                   r"clattering|tumbling|skittering)\b")
# Hedges and denials in the words just before the verb: "nearly", "threatens to",
# "does not", "without".
_HEDGED = re.compile(
    r"\b(?:doesn't|does\s+not|didn't|did\s+not|not|never|without|nor|no\s+longer|"
    r"fails?\s+to|cannot|can't|couldn't|could\s+not|unable\s+to|instead\s+of|nearly|"
    r"almost|threaten(?:s|ing)?\s+to|tries\s+to|try\s+to|trying\s+to|attempts?\s+to|"
    r"would|could|might|as\s+if|as\s+though|before\s+it\s+can)\s+(?:\w+\s+){0,4}$",
    re.I)

# Possessives that say whose a thing is. "your" is the player's after the name swap.
_POSSESSIVE = r"(?:your|his|her|their|its|[A-Z][\w'’-]*['’]s)"

# Where a hand-held thing comes FROM, which names its holder when no possessive sits on
# the thing itself: "from his hip", "as his grip fails".
_FROM_HOLDER = re.compile(
    rf"\b(?:from|out\s+of|off)\s+({_POSSESSIVE})\s+(?:\w+\s+)?"
    r"(?:hand|hands|grip|grasp|fingers|fist|hip|belt|side|waist|palm)\b", re.I)
_GRIP_HOLDER = re.compile(rf"\b({_POSSESSIVE})\s+(?:grip|grasp|fingers|hand|hold)\b", re.I)

# A body suffering a condition, physical sense only. Each row: the words, the condition
# key the engine would carry, and the tag `has_state` asks.
_CONDITION_WORDS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(?:momentarily\s+|briefly\s+|utterly\s+|completely\s+|left\s+)?"
                r"stunned\b(?![\s,]+(?:[a-z]+[\s,]+){0,2}(?:silence|look|expression|face|disbelief|surprise|"
                r"eyes|stare|gaze|onlookers|crowd|patrons|quiet|pause))", re.I),
     "stunned", "state.unable.stunned"),
    (re.compile(r"\b(?:momentarily\s+|briefly\s+|left\s+)?dazed\b(?![\s,]+(?:[a-z]+[\s,]+){0,2}(?:look|expression|"
                r"face|eyes|stare|gaze|smile|grin|onlookers|crowd|patrons))", re.I),
     "dazed", "state.unable.dazed"),
    (re.compile(r"\b(?:sprawl(?:s|ed|ing)?(?=\s+(?:on|in|across|against|onto|into|to|over|beneath|at)\b)|knock(?:s|ed)?\s+(?:\w+\s+)?"
                r"(?:flat|prone|off\s+(?:his|her|their|its|your)\s+feet|"
                r"to\s+the\s+(?:ground|floor|deck))|flat\s+on\s+(?:his|her|their|its|"
                r"your)\s+back|(?:lies|lying)\s+prone|prone)\b", re.I),
     "prone", "state.position.prone"),
    (re.compile(r"\b(?:blinded|can(?:no|')t\s+see)\b", re.I),
     "blinded", "state.senses.blinded"),
    (re.compile(r"\b(?:unconscious|out\s+cold|knock(?:s|ed)?\s+(?:\w+\s+)?out|"
                r"senseless)\b", re.I),
     "unconscious", "state.unable"),
]

_WIELDED = re.compile(
    r"\b(?:whistl\w*|swing\w*|swung|slash\w*|thrust\w*|flash\w*|arc(?:s|ed|ing)?|"
    r"cut(?:s|ting)?|bit(?:e|es|ing)|strik\w*|struck|lunge\w*|scrap\w*|glint\w*|"
    r"sing(?:s|ing)?|hiss\w*|carv\w*|stab\w*|parr\w*|rais\w*|level\w*|clatter\w*|"
    r"slam\w*|rak\w*|find(?:s|ing)?|miss\w*|slips?\s+from|in\s+your\s+hand|"
    r"your\s+grip)\b", re.I)
# The weapon described where it lies, not in a hand: "your rapier lies in the sawdust",
# "you reach for your blade", "towards where your steel fell".
_NOT_IN_HAND = re.compile(
    r"\b(?:lies|lying|lay|rests|resting|where|reach(?:es|ing)?\s+for|toward|towards|"
    r"retriev\w*|pick\w*\s+up|on\s+the\s+(?:floor|ground|boards|floorboards|deck)|"
    r"beneath|under\s+a|out\s+of\s+reach|empty)\b", re.I)


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted({w.lower() for w in words if w},
                                                   key=len, reverse=True))


def _sentences(text: str) -> list[str]:
    from .narration import _sentences as split

    return split(text)


def _unsaid(sentence: str) -> str:
    from .judgement import redact_speech

    return redact_speech(sentence)


def _hedged(sentence: str, at: int) -> bool:
    return bool(_HEDGED.search(sentence[max(0, at - 50):at]))


class _Cast:
    """Who the words in a sentence can mean: "you" is the player, "he"/"his" any
    creature here, a name the actor it names."""

    def __init__(self, scene):
        from .narration import actor_words

        self.scene = scene
        self.pc = scene.pc() if scene is not None else None
        self.others = [a for a in (scene.actors.values() if scene is not None else [])
                       if not a.is_pc]
        self.by_word: dict[str, object] = {}
        for a in self.others:
            for w in actor_words(a.name):
                self.by_word.setdefault(w, a)

    def whose(self, word: str):
        """"your" -> [pc]; "his" -> every creature here; "Borin's" -> [Borin]."""
        w = word.lower().rstrip("s").rstrip("'’")
        if w in ("your", "you"):
            return [self.pc] if self.pc is not None else []
        if w in ("hi", "his", "her", "their", "it", "its", "he", "him", "she", "them",
                 "they"):
            return list(self.others)
        a = self.by_word.get(w)
        return [a] if a is not None else list(self.others)

    def subject_before(self, sentence: str, at: int):
        """The nearest person-word before `at`: whose body the condition is on."""
        best = None
        for m in re.finditer(r"\b(you|your|he|him|his|she|her|they|them|their|it|its|"
                             r"[A-Z][\w'’-]+)\b", sentence[:at]):
            word = m.group(1)
            if word[0].isupper() and word.lower() not in ("you", "your", "he", "his",
                                                           "she", "her", "they", "it",
                                                           "its", "him", "them", "their"):
                if word.lower().rstrip("s").rstrip("'’") not in self.by_word and \
                        word.lower() not in self.by_word:
                    continue
            best = word
        return self.whose(best) if best else list(self.others)


def _down(actor) -> bool:
    return bool(getattr(actor, "is_down", False)) or getattr(actor, "hp", 1) <= 0


def _changed(changes, kinds) -> list[dict]:
    return [c for c in (changes or []) if isinstance(c, dict) and c.get("kind") in kinds]


def state_claims(text: str, scene, changes=None) -> list[tuple[str, str]]:
    """Sentences that say a hand holds or loses something, or a body suffers something,
    that the state does not carry. Returns (sentence, why) pairs, the why naming the
    fact the repair has to write to. Run on prose already in the second person."""
    if not text or scene is None:
        return []
    cast = _Cast(scene)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    def flag(sentence: str, why: str) -> None:
        if sentence not in seen:
            seen.add(sentence)
            found.append((sentence, why))

    # What left a hand this turn, and whose hand.
    dropped = _changed(changes, ("dropped",))
    taken = _changed(changes, ("stolen",))
    broken = [c for c in _changed(changes, ("item_damage",)) if c.get("destroyed")]
    let_go = {str(c.get("ref")) for c in dropped} | {str(c.get("from")) for c in taken} \
        | {str(c.get("owner") or c.get("ref")) for c in broken}
    given = {str(c.get("ref")) for c in _changed(changes, ("condition",))}

    # The names of everything carried here, beside the generic nouns.
    carried = set(_WEAPON_WORDS) | set(_PURSE_WORDS) | set(_SHIELD_WORDS)
    for a in scene.actors.values():
        carried.update(str(w).lower() for w in (a.weapons or []) if w)
        if a.equipped and a.equipped != "unarmed":
            carried.add(str(a.equipped).lower())
        if a.shield and a.shield != "none":
            carried.add(str(a.shield).lower())
    thing = re.compile(rf"\b({_alt(carried)})\b", re.I)
    # After the thing, within its own clause; before it, ending right at it.
    after_rx = re.compile(rf"^[^.!?;]{{0,30}}?\b({_LEAVES_AFTER})\b", re.I)
    before_rx = re.compile(rf"\b{_LEAVES_BEFORE}\s+(?:[\w'’-]+\s+){{0,3}}$", re.I)
    forced_rx = re.compile(rf"\b{_FORCES_BEFORE}\s+(?:[\w'’-]+\s+){{0,3}}$", re.I)
    particle_rx = re.compile(_PARTICLE_AFTER, re.I)

    for said in _sentences(text):
        # Matched with what anybody SAID blanked (same length), reported whole: a smith's
        # "when the hammer falls" is his, not the narrator's claim about a hand.
        s = _unsaid(said)
        # --- 1. a thing leaving a hand -------------------------------------------------
        for t in thing.finditer(s):
            after = after_rx.search(s[t.end():])
            ahead = s[max(0, t.start() - 40):t.start()]
            before = None if after else (
                before_rx.search(ahead)
                or (particle_rx.search(s[t.end():]) and forced_rx.search(ahead)))
            if after:
                at = t.end() + after.start(1)
            elif before:
                at = max(0, t.start() - 40) + before.start()
            else:
                continue
            if _hedged(s, at):
                continue
            # Whose: a possessive on the thing, else where it came from, else whose grip.
            own = re.search(rf"({_POSSESSIVE})\s+(?:\w+\s+)?$", s[:t.start()])
            holder = (own.group(1) if own else
                      (_FROM_HOLDER.search(s) or _GRIP_HOLDER.search(s) or [None, None])[1])
            holders = cast.whose(holder) if holder else \
                (list(cast.others) + ([cast.pc] if cast.pc is not None else []))
            if any(_down(h) for h in holders if h is not None):
                continue                     # a corpse's weapon falls; let it
            refs = {getattr(h, "ref", "") for h in holders if h is not None}
            if refs & let_go:
                continue
            item = t.group(1).lower()
            if let_go:
                losers = ["you" if cast.pc is not None and r == cast.pc.ref
                          else scene.actors[r].name for r in sorted(let_go)
                          if r in scene.actors]
                them = "you" if (holder or "").lower() == "your" else "them"
                flag(said, f"gives the lost {item} to the wrong hands: the one who lost "
                        f"hold of something this moment was {' and '.join(losers)}, "
                        f"not {them}")
            else:
                flag(said, f"says the {item} leaves a hand, and nothing was dropped, "
                        f"knocked loose or taken this moment — every {item} is where "
                        f"it was")
            break

        # --- 2. a body suffering a condition -------------------------------------------
        # Every unheld condition in the sentence goes into ONE why: naming only the first
        # let the repair keep the second ("sprawling" stayed when "stunned" was fixed).
        said_of: dict[str, list[str]] = {}
        for rx, key, tag in _CONDITION_WORDS:
            for m in rx.finditer(s):
                if _hedged(s, m.start()):
                    continue
                bodies = [b for b in cast.subject_before(s, m.start()) if b is not None]
                if not bodies:
                    continue
                if any(_down(b) or b.has_state(tag) or b.ref in given for b in bodies):
                    continue
                who = ("you" if bodies == [cast.pc] else
                       bodies[0].name if len(bodies) == 1 else "they")
                if key not in said_of.setdefault(who, []):
                    said_of[who].append(key)
                break
        for who, keys in said_of.items():
            what = " and ".join(keys)
            flag(said, f"says {who} {'are' if who in ('you', 'they') else 'is'} {what}, "
                    f"and {'you are' if who == 'you' else who + ' is'} not: nothing put "
                    f"{'that' if len(keys) == 1 else 'either'} on "
                    f"{'you' if who == 'you' else 'them'}")

        # --- 3. a weapon in a hand that holds something else ---------------------------
        pc = cast.pc
        if pc is not None:
            holding = _holding(pc)
            for m in re.finditer(rf"\byour\s+(?:\w+\s+)?({_alt(set(_WEAPON_WORDS) | {str(w).lower() for w in pc.weapons} | _ledger_names(scene, pc.ref))})\b", s, re.I):
                named = m.group(1).lower()
                if named in ("weapon",) and holding:
                    continue
                if not _WIELDED.search(s[m.end():m.end() + 60] + " " + s[:m.start()][-25:]):
                    continue
                if _NOT_IN_HAND.search(s):
                    continue
                if holding is None:
                    flag(said, f"puts a {named} in your hand, and your hands are empty"
                            + _where_it_lies(scene, pc.ref))
                    break
                generic = named in _WEAPON_WORDS and named not in {
                    str(w).lower() for w in pc.weapons} | _ledger_names(scene, pc.ref)
                if not generic and named != holding:
                    flag(said, f"puts your {named} in your hand, and you are holding the "
                            f"{holding}" + _where_it_lies(scene, pc.ref, named))
                    break
        # A creature's weapon only when nobody here, standing or fallen, holds one: the
        # dead keep theirs `equipped`, and a corpse's sap may clatter.
        armed = [a for a in cast.others if _holding(a)]
        standing = [a for a in cast.others if not _down(a)]
        if standing and not armed:
            m = re.search(rf"\b(?:his|her|their|its)\s+(?:\w+\s+)?({_alt(_WEAPON_WORDS)})\b",
                          s, re.I)
            if m and _WIELDED.search(s[m.end():m.end() + 60]) and not _NOT_IN_HAND.search(s):
                flag(said, f"puts a {m.group(1).lower()} in a hand that holds nothing — "
                        f"nobody facing you here is armed")
    return found


def _holding(actor) -> str | None:
    """The weapon in this creature's hand, or None for an empty one. A formed class
    weapon counts (it answers to "unarmed" and is a blade all the same)."""
    key = (actor.equipped or "unarmed").strip().lower()
    try:
        w = actor.weapon(key)
    except Exception:  # an unknown name is still something held
        return key if key != "unarmed" else None
    if w.get("granted_by"):
        return str(w.get("name") or key).lower()
    if key in ("unarmed", "unarmed strike", "") or actor.natural_weapon(key) is not None:
        return None
    return key


def _ledger_names(scene, ref: str) -> set[str]:
    return {str(r.get("from_") or "").lower() for r in getattr(scene, "props", [])
            if r.get("owner") == ref and r.get("from_")}


def _where_it_lies(scene, ref: str, named: str = "") -> str:
    for r in getattr(scene, "props", []):
        if r.get("owner") == ref and r.get("state") in ("intact", "broken") \
                and not r.get("held_by") and (not named or r.get("from_") == named):
            return f" — your {r.get('from_')} is lying on the floor"
    return ""
