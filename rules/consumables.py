"""Drinking it, throwing it, and putting it on a blade.

A crafted potion used to be a paragraph. It had a name, a rarity, a potency multiplier and
a list of effects written for a person to read, and nothing in the engine could do anything
with any of it — the player threw a tincture at a beast and got narration, because
narration was the only thing available.

`Stock.specs` closed half of that: the same effects the card shows, in the structured form
`rules/effectspec.py` defines. This closes the other half, by turning those specs into
intents the engine already knows how to resolve. Nothing new is invented — a potion that
heals emits the `heal` op, one that poisons emits `save` and `ability_damage`, and both go
through the same validation as anything the GM proposes.

**Three ways to use one, and the difference is real.**

  drink   the whole dose, on yourself or somebody you can touch
  throw   a splash weapon: a ranged touch attack, and 1e's splash rules
  coat    a blade, if the thing is harmful — it waits on the weapon for the next hit

**Potency is applied here and nowhere else.** A chain's multiplier is a property of the
result, stated once on the card beside the rarity; stamping it onto every effect line was
noise on every card in the app. But it has to reach the dice eventually, and this is the
only place that rolls them.

**What it will not do.** A spec `effectspec.executable()` says the engine cannot resolve is
carried into the outcome as text for the GM to narrate, never silently dropped and never
guessed at. An item whose every effect is prose is still a usable item; it just does what
the fiction says rather than what the engine does.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import effectspec
from .tables import SAVES

# Effects that hurt whoever receives them. A thing made of these is a poison: it is worth
# throwing, and it is worth putting on a blade. Anything else is a draught.
HARMFUL = {"damage", "ability_damage", "ability_drain", "bleed", "apply_condition",
           "save_gate"}

# What a splash weapon does to everyone around the square it lands in. 1e: "splash weapons
# deal 1 point of splash damage to all creatures within 5 feet of the target".
SPLASH_RADIUS_FT = 5

_DICE = re.compile(r"^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.I)


@dataclass
class Use:
    """One consumable being used, resolved into things the engine can do."""
    item: str
    how: str                      # drink | apply | throw | coat
    intents: list[dict] = field(default_factory=list)
    # Effects the engine cannot resolve, kept verbatim for the GM to narrate. Never
    # dropped: an item that quietly does less than its card says is worse than one that
    # says "and the rest is up to you".
    narrate: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def is_harmful(stock) -> bool:
    """Would this hurt whoever got it? Decides what may be thrown and what may coat a
    blade, and it is read off the effects rather than the name — "Purified Draught of
    Skull Orchid" is not made safe by being called one."""
    return any(str(s.get("type")) in HARMFUL for s in _specs(stock))


# --- what is harm, and what is a poison -----------------------------------------------------
#
# Measured on the shipped corpus: 99 of the 178 effects the 161 ingredients carry are harm,
# and every one of them was printed under "Effects" beside the bonuses. The Drawbacks
# section said one boilerplate sentence that named nothing.


def _branches(spec: dict) -> list[dict]:
    return list(spec.get("on_failure") or []) + list(spec.get("on_success") or [])


def _poisonous(spec: dict) -> bool:
    """Harm that makes the thing a poison: what `HARMFUL` names, minus the bare gate.

    The gate is excluded because a save on its own poisons nobody. It is the *body* of a
    poison that decides there is one, and the save is then attached to it.
    """
    kind = str(spec.get("type", ""))
    return kind in HARMFUL and kind != "save_gate"


def hurts(spec: dict) -> bool:
    """Whether one effect is harm — the question the Drawbacks section asks.

    Wider than `HARMFUL` by exactly one case, and the difference is deliberate. A -2
    penalty is harm on a card, but it is not a poison: it does not make a draught worth
    throwing at anybody or worth putting on a blade, which is the only question `HARMFUL`
    is asked. 20 of the corpus's 178 effects are penalties, and "-2 to all actions while
    in the area" sitting under Effects next to "+5 save vs poison" is what this separates.

    A bare `save_gate` is *not* harm on its own. 41 of the corpus's 59 gates carry nothing
    at all — they are the entry's own crafting DC, restated at the end of the description
    ("Cave Star ... DC: 10.") and swept up by the extractor's bare-DC fallback. Filing
    those under Drawbacks would have invented 41 poisons that poison nobody. A gate earns
    its place by gating something, either in its own branches or through the source it
    came in with, which `poisons` below works out.
    """
    kind = str(spec.get("type", ""))
    if kind == "save_gate":
        return any(hurts(x) for x in _branches(spec))
    if kind in HARMFUL:
        return True
    if kind.endswith("_mod"):
        try:
            return int(spec.get("amount", 0)) < 0
        except (TypeError, ValueError):
            return False
    return False


def _lower_first(s: str) -> str:
    """"Causes nauseated" reads as a clause, not a sentence, once it is joined to a save.

    Left alone when the second character is also upper case, so "DR 3/—" does not come
    back as "dR 3/—".
    """
    return s[0].lower() + s[1:] if len(s) > 1 and not s[1].isupper() else s


@dataclass
class Poison:
    """One source's harmful cluster: the save that gates it, what it does, and where it
    came from.

    Grouped rather than listed flat because the extractor finds a poison in pieces. Dragon
    Flower's card read "1d6 Constitution damage", "Fortitude DC 25" and "Causes nauseated"
    as three unrelated lines, and the save that gates the damage looked like an effect of
    its own. 1e writes a poison as one thing: a save, and what happens when you fail it.

    The source is the ingredient's own name rather than an invented one. A generated name
    would be a fact nobody wrote, and "Dragon Flower" is the name the player picked off the
    shelf.
    """
    source: str = ""
    # The gate spec itself, kept rather than only its numbers, so whatever consumes this
    # can tell that the gate has been accounted for and must not be listed again.
    gate: dict | None = None
    effects: list[dict] = field(default_factory=list)

    @property
    def dc(self) -> int | None:
        if not self.gate or self.gate.get("dc") in (None, ""):
            return None
        try:
            return int(self.gate["dc"])
        except (TypeError, ValueError):
            return None

    @property
    def save(self) -> str:
        """"fort", "ref", "will" — or empty, which 55 of the 59 gates in the corpus are.

        The source states a bare DC and never says which save; choosing one would put a
        fact on the card that nobody wrote.
        """
        return str((self.gate or {}).get("target") or "").lower()

    @property
    def save_line(self) -> str:
        dc = self.dc
        if dc is None:
            return ""
        return f"{SAVES.get(self.save, '')} DC {dc}".strip()

    def branch_of(self, spec: dict) -> str:
        """Which verdict of the save this body belongs to: "success" only for a body an
        author wrote under the gate's `on_success` (the poison that still bites whoever
        resists it); everything else, the extractor's bare-gate bodies included, is
        what failing costs. By identity, as `poisons` collected them."""
        return "success" if any(spec is s for s in (self.gate or {}).get("on_success")
                                or []) else "failure"

    @property
    def lines(self) -> list[str]:
        return [effectspec.render(s) for s in self.effects]

    @property
    def harm(self) -> str:
        """What failing the save costs, as one clause.

        Composed here rather than in the template so the rule for joining them lives in
        one language. A page that rebuilt this line in JavaScript would be the second copy
        that goes stale.
        """
        return ", ".join(_lower_first(line) for line in self.lines)

    @property
    def body(self) -> str:
        """The save and what failing it costs, without the source's name in front."""
        gate = self.save_line
        return f"{gate} or {self.harm}" if gate else self.harm

    @property
    def line(self) -> str:
        """The card line. Keeps the "Source: mechanic" shape the effect list already uses,
        so the two panels read the same way and the page can dim the source on both."""
        return f"{self.source}: {self.body}" if self.source else self.body

    def as_dict(self) -> dict:
        return {"source": self.source, "save": self.save, "dc": self.dc,
                "save_line": self.save_line, "lines": self.lines, "harm": self.harm,
                "body": self.body, "line": self.line}


@dataclass
class Sorted:
    """A list of effects, sorted into what it does for you and what it does to you.

    `benefits` holds the same dict objects that were passed in, not copies, so a caller
    holding a line beside each spec can match them back by identity.
    """
    benefits: list[dict] = field(default_factory=list)
    poisons: list[Poison] = field(default_factory=list)
    penalties: list[dict] = field(default_factory=list)


def poisons(specs: list[dict], source: str = "") -> list[Poison]:
    """Every harmful cluster in a list of effects, one poison per source that carries harm.

    Grouped by `from` — the ingredient each effect was read out of — because that is the
    only thing tying a save to the damage it gates. Taking "the first save in the list"
    instead worked for a one-ingredient item and quietly dropped the second poison's save
    from anything made of two.
    """
    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    for spec in specs:
        key = str(spec.get("from") or source)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(spec)

    out: list[Poison] = []
    for key in order:
        group = groups[key]
        gates = [s for s in group if str(s.get("type")) == "save_gate"]
        # An authored gate carries its own branches and is a whole poison by itself. The
        # extractor never nests, so its gates arrive bare and belong to whatever else
        # their source brought in with them.
        for gate in gates:
            branch = [x for x in _branches(gate) if _poisonous(x)]
            if branch:
                out.append(Poison(source=key, gate=gate, effects=branch))
        body = [s for s in group if _poisonous(s)]
        if body:
            bare = next((g for g in gates if not _branches(g)), None)
            out.append(Poison(source=key, gate=bare, effects=body))
    return out


def sort_harm(specs: list[dict], source: str = "") -> Sorted:
    """Split a list of effects into benefits, poisons and loose penalties."""
    found = poisons(specs, source)
    claimed = [s for p in found for s in p.effects]
    claimed += [p.gate for p in found if p.gate is not None]
    pen = [s for s in specs
           if not any(s is c for c in claimed) and hurts(s) and not _poisonous(s)]
    claimed += pen
    return Sorted(benefits=[s for s in specs if not any(s is c for c in claimed)],
                  poisons=found, penalties=pen)


def _specs(stock) -> list[dict]:
    if isinstance(stock, dict):
        return [dict(s) for s in (stock.get("specs") or [])]
    return [dict(s) for s in (getattr(stock, "specs", None) or [])]


def _field(stock, name, default=None):
    if isinstance(stock, dict):
        return stock.get(name, default)
    return getattr(stock, name, default)


def scale(dice: str, potency: float) -> str:
    """Apply a chain's potency to a dice expression.

    Scales the flat part rather than the number of dice, because "1d6 at 125%" as 1.25d6
    is not a thing anyone can roll. 1d6 at 125% becomes 1d6+2: a quarter of the average
    (3.5), rounded the way `crafting` rounds — benefits up, and this is only ever called
    on the thing the player made on purpose.
    """
    text = str(dice or "")
    # The corpus's range form, normalised to real dice before anything else: "1-4" is
    # 1d4 and "2-8" is 1d7+1. Left alone, a range fell through the notation match and
    # potency silently never applied — a 506% Comfrey Tea healed exactly what a plain
    # one did, which is the player's brewing thrown away without a word.
    r = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", text)
    if r and int(r.group(2)) > int(r.group(1)):
        lo, hi = int(r.group(1)), int(r.group(2))
        flat0 = lo - 1
        text = f"1d{hi - lo + 1}" + (f"+{flat0}" if flat0 else "")
    m = _DICE.match(text)
    if not m or abs(potency - 1.0) < 0.01:
        return text
    count, sides = int(m.group(1)), int(m.group(2))
    flat = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
    average = count * (sides + 1) / 2
    extra = average * (potency - 1.0)
    flat += int(extra + 0.999) if extra > 0 else int(extra)
    if flat > 0:
        return f"{count}d{sides}+{flat}"
    if flat < 0:
        return f"{count}d{sides}{flat}"
    return f"{count}d{sides}"


# The bonus families a chain's potency raises (dice are `scale`'s).
SCALED_BONUSES = ("save_mod", "skill_mod", "ability_mod", "combat_mod")


def scaled_bonus(amount, potency: float) -> int:
    """A flat bonus at the strength a brew of this potency delivers. The ONE reader.

    Potency scales benefits the way it scales dice — the author's distill rule is about
    the primary effect, not only the numbered ones — and rounds up, per the house
    rounding. Penalties are left alone: a stronger brew is not a worse one.

    One function because two readers disagreed (playtest 2026-09-30, the Power leaf
    aside): the owner's homebrew leaf says +20 Str and +20 Con, the brewed tea's card
    printed "+20 Strength", and drinking it landed +26 — a herbalist's brew is potency
    1.30 (brew +25%, +5% per herbalist level) and this rule applied it, while the card
    was rendered from the unscaled spec. The card now asks this function too
    (`crafting.sift(potency=...)`), so the number on the jar is the number that lands.
    """
    try:
        amount = int(str(amount if amount is not None else 0).strip() or 0)
    except ValueError:
        return 0
    if amount > 0 and potency > 1.0:
        amount = int(amount * potency + 0.999)
    return amount


def _spec_to_intents(spec: dict, target: str, potency: float, because: str) -> list[dict]:
    """One structured effect as engine intents, or [] if the engine cannot run it."""
    kind = str(spec.get("type", ""))
    dice = spec.get("dice") or spec.get("amount")

    if kind == "heal":
        # "Heals 4 non-lethal" cures the beating, not the wound. The spec says which
        # (`lethality`, effectspec's "Heals which" field) and this branch dropped it, so
        # all 39 non-lethal heals in the corpus restored real hit points: a liniment
        # brought a taster at 0 back to 1 (Lane T, 2026-10-02).
        params = {"amount": scale(str(dice), potency)}
        if str(spec.get("lethality", "")).lower() == "nonlethal":
            params["nonlethal"] = True
        return [{"op": "heal", "actor": target, "because": because, "params": params}]

    if kind == "temp_hp":
        return [{"op": "temp_hp", "actor": target, "because": because,
                 "params": {"amount": scale(str(dice), potency),
                            "source": spec.get("from") or "the draught"}}]

    if kind == "damage":
        return [{"op": "damage", "actor": target, "because": because,
                 "params": {"to": target, "amount": scale(str(dice), potency),
                            "type": spec.get("damage_type") or "untyped"}}]

    if kind in ("ability_damage", "ability_drain"):
        return [{"op": "ability_damage", "actor": target, "because": because,
                 "params": {"to": target, "ability": spec.get("target") or "con",
                            "amount": scale(str(dice), potency),
                            "drain": kind == "ability_drain"}}]

    if kind == "apply_condition":
        params = {"condition": spec.get("target") or spec.get("condition") or "sickened",
                  "to": target}
        duration = spec.get("duration")
        if isinstance(duration, dict) and duration.get("amount"):
            params["duration"] = {"amount": duration.get("amount"),
                                  "unit": duration.get("unit", "round")}
        return [{"op": "condition", "because": because, "params": params}]

    if kind in SCALED_BONUSES:
        amount = scaled_bonus(spec.get("amount", 0), potency)
        out = [{"op": "buff", "actor": target, "because": because,
                "params": {"type": kind, "target": spec.get("target", ""),
                           "amount": amount, "to": target,
                           "source": spec.get("from") or "the preparation",
                           # The channel the author already filled in. Dropped here
                           # for the life of the feature, so every brew stacked with
                           # every other brew of its own kind.
                           **({"bonus_type": spec["bonus_type"]}
                              if spec.get("bonus_type") else {}),
                           **({"duration": spec["duration"]}
                              if isinstance(spec.get("duration"), dict) else
                              {"duration": {"amount": 1, "unit": "hour"}}),
                           **({"note": spec["note"]} if spec.get("note") else {})}}]
        return out

    if kind == "speed":
        # The channel went live in stage 2 (speed_feet reads the funnel) and nothing
        # could fill it: a potion of longstrider still produced no intents. `speed` is
        # a modifier like any other once there is a reader for it.
        return [{"op": "buff", "actor": target, "because": because,
                 "params": {"type": "speed",
                            "target": str(spec.get("target", "") or "land"),
                            "amount": int(spec.get("amount", 0) or 0), "to": target,
                            "source": spec.get("from") or "the preparation",
                            **({"bonus_type": spec["bonus_type"]}
                               if spec.get("bonus_type") else {}),
                            **({"duration": spec["duration"]}
                               if isinstance(spec.get("duration"), dict) else
                               {"duration": {"amount": 1, "unit": "hour"}})}}]

    if kind in ("resistance", "damage_reduction", "immunity", "vulnerability"):
        # The branch these four never had. Each was marked executable-ish in the
        # catalogue with a `blocked` note saying a consumable granting one is "recorded
        # and narrated — nothing wears off yet", and the honest consequence was that
        # drinking one produced no intents at all: the dose spent, nothing applied, no
        # error. They wear off now, so they can be granted.
        return [{"op": "defence", "actor": target, "because": because,
                 "params": {"kind": kind,
                            "against": str(spec.get("target", "") or ""),
                            "amount": int(spec.get("amount", 0) or 0),
                            "bypass": str(spec.get("bypass", "") or ""),
                            "to": target,
                            "source": spec.get("from") or "the preparation",
                            **({"duration": spec["duration"]}
                               if isinstance(spec.get("duration"), dict) else
                               {"duration": {"amount": 1, "unit": "hour"}})}}]

    if kind == "remove_condition":
        # `ends`, the op's own word (`_op_condition`). This read `remove` until 2026-10-02,
        # which the op table has never taken: every jar with an "Ends X" line (cowslip's
        # "Ends paralyzed") raised at parse when drunk. Found by Lane C's taste of all 161.
        return [{"op": "condition", "because": because,
                 "params": {"condition": spec.get("target") or "", "to": target,
                            "ends": True}}]

    return []


def _gate_intent(poison: Poison, target: str, because: str, label: str = "") -> list[dict]:
    """A poison's saving throw, emitted once before what it does.

    The extractor produces `save_gate` as its own effect — "Fortitude DC 25" sits beside
    "1d6 Constitution damage" rather than wrapping it — so the two are stitched back
    together by `poisons()`. Without this the save is a line on a card that nothing ever
    rolls.

    Falls back to Fortitude when the source names a DC and no save, which is 55 of the
    corpus's 59 gates. Poison is a Fortitude affair in 1e, and rolling the wrong save is
    still better than the alternative here: not rolling at all.

    `label` names this save to the bodies behind it (`_gated`), so the engine can take
    them off the queue when the save is made (`Engine._link_gates`).
    """
    dc = poison.dc
    if dc is None:
        return []
    return [{"op": "save", "actor": target, "because": because,
             "params": {"save": poison.save or "fort", "dc": {"value": dc}},
             "visibility": "player", **({"gate": label} if label else {})}]


def _gated(intents: list[dict], label: str, on: str) -> None:
    """Mark a poison's body intents as its save's to decide. In place.

    Rolling the save first was never enough: until 2026-10-02 the save and its body went
    to the engine side by side and the body landed whatever the save said — a successful
    Fortitude save against a jar of dragon flower still took the Constitution and the
    nausea. Only called when a save was actually emitted; a body with no gate in front of
    it is harm with no save, and lands.
    """
    for intent in intents:
        intent["gated_by"] = label
        intent["gated_on"] = on


# Words that mean "a jar" and carry nothing about WHICH jar. "My healing potion" and a
# Healing Draught are the same thing to the player; Inform's parser matches an object
# on any word of its name and asks when two still fit, and that is the shape here.
JAR_WORDS = frozenset({
    "potion", "potions", "draught", "draughts", "elixir", "elixirs", "tincture",
    "tinctures", "tea", "teas", "philtre", "philter", "salve", "salves", "poultice",
    "poultices", "vial", "vials", "flask", "flasks", "tonic", "tonics", "brew", "brews",
    "remedy", "remedies", "antidote", "antidotes", "oil", "oils", "balm", "balms",
    "unguent", "jar", "jars", "bottle", "bottles", "dose", "doses", "my", "the", "a",
    "an", "of", "some"})


def resolve_stock(stock: dict, said: str) -> tuple[str | None, list[str]]:
    """The satchel entry the player means by `said`, or the candidates that still fit.

    Measured on 2026-09-03 with the stage-8 inverse probe: "I drink my healing
    potion" with a Healing Draught in the satchel came back as `use_item item="healing
    potion"`, and the door — an exact-id lookup — printed "not carrying healing
    potion. They have: healing-draught#1" three times out of three. The player knew
    exactly what they had; the engine refused them over a synonym.

    Exact id or base name wins. Otherwise every content word of `said` (the jar words
    above stripped) is matched against the words of each entry's id and base; the best
    score above zero wins outright when it is unique. Nothing named and exactly one
    jar carried is that jar; nothing named and several carried is a question, and the
    caller prints the candidates rather than guessing — a potion drunk by guess would
    be the poison.
    """
    said_l = " ".join(str(said or "").lower().split())
    if not stock:
        return None, []
    for iid, s in stock.items():
        if said_l in (iid.lower(), str(getattr(s, "base", "") or "").lower()):
            return iid, [iid]
    # The `#N` dose suffix is bookkeeping, not a word: "nothing#1" must not match
    # "tincture#1" on the 1.
    def _words(text: str) -> list[str]:
        return [w for w in re.split(r"[^a-z0-9]+", re.sub(r"#\d+", " ", text.lower()))
                if w and not w.isdigit()]

    content = [w for w in _words(said_l) if w not in JAR_WORDS]
    scored: list[tuple[int, str]] = []
    for iid, s in stock.items():
        words = set(_words(f"{iid} {getattr(s, 'base', '')}"))
        score = sum(1 for w in content if w in words or any(
            x.startswith(w) or w.startswith(x) for x in words if len(w) > 3))
        if score:
            scored.append((score, iid))
    if scored:
        best = max(sc for sc, _ in scored)
        hits = [iid for sc, iid in scored if sc == best]
        return (hits[0] if len(hits) == 1 else None), hits
    if not content and len(stock) == 1:
        only = next(iter(stock))
        return only, [only]
    return None, (sorted(stock) if not content else [])


# --- where on the body a preparation goes (the owner, 2026-10-02: "a use button for
# products that lets you choose based on the ingredient/products tagged places") ---------
#
# Every herbal effect carries a `route` (docs/herbalism-contracts.md §2): swallowed, on
# the skin, in the eyes, on a wound, breathed in, or `external` (alchemy's, never a
# remedy's). Using a product is choosing one of those, and only what works THERE lands:
# an eye salve's sight is in the eyes, its wound-closing is on the wound. Project
# Zomboid's health panel is the prior art: the treatment menu offers only what the item
# and the place allow, and lets you treat somebody else close by.
ROUTE_USE = {
    # route: (menu label, verb for the tell, where it goes on the target)
    "ingest": ("Drink it", "drinks", ""),
    "eyes": ("On the eyes", "puts", "eyes"),
    "wound": ("On a wound", "binds", "wound"),
    "skin": ("On the skin", "rubs", "skin"),
    "inhale": ("Breathe it in", "breathes in", ""),
}


def routes_of(stock) -> list[str]:
    """The places this item can go, in a fixed order, each with something that works
    there. A herbal product also has to be able to carry the route at all (its form's
    `routes`: a tincture is drops on the tongue, never an eye salve), so the menu offers
    a place only when the form allows it AND one of its effects lands there."""
    from .ingredients import route_of

    # Every effect counts, run or narrated: one the engine cannot execute is still told to
    # the GM where it lands (`_resolve`), never dropped, so its place is still a place.
    have = {route_of(s) for s in _specs(stock) if str(s.get("type")) != "save_gate"}
    form = _field(stock, "form", None)
    if form:
        from .crafting import product_row

        allowed = set((product_row(form) or {}).get("routes") or ())
        if allowed:
            have &= allowed
    return [r for r in ROUTE_USE if r in have]


def _on_route(specs: list[dict], route: str) -> list[dict]:
    """The specs that work through `route`, a poison's save travelling with its body."""
    from .ingredients import route_of

    kept = [s for s in specs if route_of(s) == route]
    for p in poisons(specs, source=""):
        if p.gate is not None and any(any(b is k for k in kept) for b in p.effects) \
                and not any(p.gate is k for k in kept):
            kept.append(p.gate)
    return kept


def plan(stock, how: str = "drink", target: str = "pc",
         because: str = "", route: str = "") -> Use:
    """What using this item actually does, as intents the engine can validate.

    `apply` with a `route` puts it where the player chose (eyes, a wound, the skin,
    breathed in) and only that route's effects land. `drink` is the swallowed route: a
    salve drunk does none of what it does on the skin, and an eye-wash's sight does not
    come from swallowing it. Effects with no route read as swallowed, so every jar made
    before routes existed drinks exactly as it did."""
    how = (how or "drink").strip().lower()
    route = (route or "").strip().lower()
    name = _field(stock, "name") or _field(stock, "base") or "the preparation"
    potency = float(_field(stock, "potency", 1.0) or 1.0)
    specs = _specs(stock)
    use = Use(item=str(name), how=how)

    if how not in ("drink", "throw", "coat", "apply"):
        use.problems.append(f"{how!r} is not a way to use something; "
                            f"drink, apply, throw or coat")
        return use
    # A jar with no structured effects at all (a bought antitoxin, which the GM narrates)
    # drinks as it always did: there is nothing to sort by place, and refusing it made the
    # counter's potions undrinkable (caught by tests/test_sheet_pages.py at the change).
    if how in ("drink", "apply") and (specs or how == "apply"):
        route = "ingest" if how == "drink" else route
        if route not in ROUTE_USE:
            use.problems.append(f"say where it goes: {', '.join(ROUTE_USE)}")
            return use
        offered = routes_of(stock)
        if route not in offered:
            where = ROUTE_USE[route][0].lower()
            use.problems.append(
                f"nothing in {name} works {('when swallowed' if route == 'ingest' else where)}"
                + (f"; it works {', '.join(ROUTE_USE[r][0].lower() for r in offered)}"
                   if offered else ""))
            return use
        specs = _on_route(specs, route)
    # Throwing needs something to hurt whoever it lands on. Painting a blade does not:
    # a weapon oil that sharpens the edge or makes it count as magic is the whole
    # point of oils, and gating `coat` on harm refused four of the alchemist's own
    # recipes — oil of magic weapon, magic fang, align weapon and keen edge — with
    # "does nothing harmful, so there is nothing to put on a blade". A benign coating
    # is declared by its maker (`how` says coat) and buffs the wielder rather than
    # poisoning the target.
    declared = [str(x).lower() for x in (_field(stock, "how", []) or [])]
    benign_coat = how == "coat" and "coat" in declared
    if how == "throw" and not is_harmful(stock):
        use.problems.append(
            f"{name} does nothing harmful, so there is nothing to throw at anybody")
        return use
    if how == "coat" and not is_harmful(stock) and not benign_coat:
        use.problems.append(
            f"{name} does nothing harmful, so there is nothing to put on a blade")
        return use
    if not _field(stock, "count", 1):
        use.problems.append(f"no {name} left")
        return use

    why = because or f"{name}, {how}"
    if benign_coat:
        # The oil is on your own weapon, so its bonuses are yours. Aimed at the wielder
        # rather than the target — the opposite of a poison, and the reason `coat` could
        # not simply be let through unchanged.
        target = "pc"
    # Each poison's own save, rolled before the harm it gates. Grouped rather than "the
    # first gate in the list", so a compound made of two poisonous ingredients rolls both
    # saves; before, the second one's save was never rolled at all.
    found = poisons(specs, source=str(name))
    claimed = [s for p in found for s in p.effects] + [p.gate for p in found if p.gate]
    for n, poison in enumerate(found):
        label = f"poison-{n}"
        gate = _gate_intent(poison, target, why, label)
        use.intents.extend(gate)
        for spec in poison.effects:
            start = len(use.intents)
            _resolve(spec, target, potency, why, use)
            if gate:
                _gated(use.intents[start:], label, poison.branch_of(spec))
    for spec in specs:
        if str(spec.get("type")) == "save_gate" or any(spec is c for c in claimed):
            continue
        _resolve(spec, target, potency, why, use)
    return use


def _resolve(spec: dict, target: str, potency: float, because: str, use: Use) -> None:
    """One effect into the outcome: as intents if the engine can run it, as a line for the
    GM if it cannot. Never silently nothing — an item that quietly does less than its card
    says is worse than one that says "and the rest is up to you"."""
    if not effectspec.executable(spec):
        use.narrate.append(effectspec.render(spec))
        return
    made = _spec_to_intents(spec, target, potency, because)
    if made:
        use.intents.extend(made)
    else:
        # Executable in principle, no mapping here yet. Still the GM's to narrate.
        use.narrate.append(effectspec.render(spec))


@dataclass
class Coating:
    """A harmful preparation waiting on a weapon.

    One hit, then it is gone — 1e poisons are a dose, not an enchantment. Held on the
    actor rather than on the weapon entry because `Actor.weapons` is a list of plain
    strings, and the alternative was giving every torch and rope a coating field.
    """
    item: str
    weapon: str = ""
    specs: list[dict] = field(default_factory=list)
    potency: float = 1.0
    uses_left: int = 1

    def as_dict(self) -> dict:
        return {"item": self.item, "weapon": self.weapon, "specs": self.specs,
                "potency": self.potency, "uses_left": self.uses_left}


def coating_from_dict(d: dict) -> Coating:
    return Coating(
        item=str(d.get("item", "")), weapon=str(d.get("weapon", "")),
        specs=[dict(s) for s in (d.get("specs") or [])],
        potency=float(d.get("potency", 1.0) or 1.0),
        uses_left=int(d.get("uses_left", 1) or 0),
    )


def coating_intents(coating: Coating, target: str) -> list[dict]:
    """What a coated blade delivers when it lands.

    Poison by poison, so a blade painted with a two-ingredient brew rolls a save for each
    of them rather than for whichever one the extractor happened to list first.
    """
    why = f"{coating.item} on the blade"
    found = poisons(coating.specs, source=coating.item)
    claimed = [s for p in found for s in p.effects] + [p.gate for p in found if p.gate]
    out: list[dict] = []
    for n, poison in enumerate(found):
        label = f"poison-{n}"
        gate = _gate_intent(poison, target, why, label)
        out.extend(gate)
        for spec in poison.effects:
            if effectspec.executable(spec):
                made = _spec_to_intents(spec, target, coating.potency, why)
                if gate:
                    _gated(made, label, poison.branch_of(spec))
                out.extend(made)
    for spec in coating.specs:
        if str(spec.get("type")) == "save_gate" or any(spec is c for c in claimed):
            continue
        if effectspec.executable(spec):
            out.extend(_spec_to_intents(spec, target, coating.potency, why))
    return out


__all__ = ["Coating", "HARMFUL", "Poison", "SPLASH_RADIUS_FT", "Sorted", "Use",
           "coating_from_dict", "coating_intents", "hurts", "is_harmful", "plan",
           "poisons", "scale", "sort_harm"]
