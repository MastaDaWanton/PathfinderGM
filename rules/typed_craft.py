"""A craft typed at the table: the base item, made for real (the engine's `make` op).

The report, 2026-10-28: "My wife tries to level up blacksmithing through narration and
didn't get real items or experience." Probed before any change: of eleven typed craft
lines ("I forge a dagger at the anvil", "I brew a basic healing draught", "I tan this hide
into leather" …) the reader filed ten as `other` and one as `cast`. `other` owes no op, so
nothing was rolled, nothing was spent, nothing was made, and the narrator wrote the forging
anyway. The only craft op the plan could write (`craft`) paid mastery and made no item.

The owner's ruling the same day: "we should try to direct people to the forge menu but i
think you should allow the crafting of the base weapons through narration", for every
craft. So a typed craft line makes the craft's SIMPLEST form of the thing — the plain
book item, the craft's base recipe — by the bench's own rules, and anything finer is
refused in words that send the player to the bench.

**What "the bench's own rules" means here.** Each craft's bench is a chain of steps
(`plan_step` in each craft's module), each one a d20 against the step's DC, its time, its
materials, its failure rule and its mastery. A typed line walks the same chain the bench
would, step by step, choosing for itself only what the bench leaves to the player — which
pieces go in which slot, and the minigame — and choosing them plainly:

* the plainest materials carried (common rank, a named common one honoured);
* no optional work (no quench, temper, hone, fold, finish, mod, catalyst);
* no masterwork aim;
* the minigame's place taken by the plain book quality, Sound (quality index 1, the
  forge's own name for "plain": `blacksmith._OLD_QUALITY_INDEX`, and the quality whose
  item name carries no prefix, `blacksmith.work_name`), never above the step's ceiling.

Prior art (researched 2026-10-28, sources in docs/typed-crafting.md): Achaea's `FORGE`
makes the whole item from one typed command at a lit forge, and its older system made a
crude item first and refined it in a separate step — the same split as base here and finer
at the bench; Skyrim makes at the forge and improves at another station. Inform 7's check
rules are the refusal model: a requirement that is not met is named ("You can hardly
photograph without a camera") and the action stops before anything changes. DragonRealms'
seven-to-ten typed commands per item are the shape refused: its players scripted them
away. Kingdom Come's auto-brew withheld the hand-brew's bonus, which is why the typed line
pays the step's own mastery and never a quality bonus the minigame would have earned.

Every step is settled by the craft's own settle functions — the same ones the bench's
views call (`blacksmith.settle_made`, `settle_miss` …) — so the failure rule, the batch's
mastery and the first-work bonuses have one copy each.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from . import worldclass as wc
from . import words as english

# The five crafts, the closed choice the reader writes (`gm/interpret.CRAFTS` is the same
# tuple) and the world-class track each one levels.
CRAFTS: tuple[str, ...] = ("blacksmith", "leatherworker", "alchemist", "herbalist",
                           "enchanter")

# The quality a typed line makes: the plain book item (module docstring).
PLAIN_QUALITY = 1

# Each craft's bench, as the table names it: the key the page opens it by (the turn
# response's `bench`, 02-state.js) and the words the tell sends the player to it with.
BENCHES: dict[str, dict] = {
    "blacksmith": {"key": "forge", "name": "the forge bench",
                   "finer": "better metals, quenching and tempering, honing, masterwork "
                            "and finishes"},
    "leatherworker": {"key": "leather", "name": "the leather bench",
                      "finer": "the fine tannages, cut hides, grades, marks and masterwork"},
    "alchemist": {"key": "alchemy", "name": "the alchemy bench",
                  "finer": "catalysts, essences, refining and the stronger mixtures"},
    "herbalist": {"key": "bench", "name": "the herb bench",
                  "finer": "tinctures, elixirs, concentrating a dose and the rarer herbs"},
    "enchanter": {"key": "enchant", "name": "the enchanting circle",
                  "finer": "every enchantment: the circle, the essences and the binding"},
}


def pointer(craft: str) -> str:
    """The sentence a typed craft's tell ends on: the bench exists for finer work.

    Short, and naming no finer work. Measured live 2026-10-28: the first pointer listed it
    ("Finer work — better metals, quenching and tempering, honing, masterwork and finishes
    — is done at the forge bench") on the tell of a REFUSED mithral longsword, and the
    planned narrator's fact slot wrote "quenching and tempering the rare metal to create a
    masterwork blade. The mithral longsword emerges with a flawless finish" — the list
    dressed as the deed. The shape of the tell became the shape of the beat (CLAUDE.md).
    The list lives on the line under the beat, which code writes (`bench_line`).

    Conditional since 2026-11-04: "Finer work is done at the leather bench" was the only
    place a typed belt's tell named, and the narrator put the player at that bench on run
    after run of the diagnosis bench (mechanism 7) — "would be" is a bench not used, and
    the make op's tell now opens on where the work IS done (`Engine._op_make`)."""
    b = BENCHES.get(craft) or {}
    return f"Finer work would be done at {b.get('name', 'the bench')}."


def bench_line(craft: str) -> str:
    """The line under the beat, beside the bench's button (play/views.py
    `_point_to_the_bench`): what the bench is for, which the tell must not carry."""
    b = BENCHES.get(craft) or {}
    return (f"For finer work — {b.get('finer', 'anything beyond the plain item')} — "
            f"{b.get('name', 'the bench')} is open to you.")


@dataclass
class Refusal:
    """Why the typed craft cannot go on, in the player's words (Inform's check rule)."""
    why: str
    code: str = "cannot_craft"


@dataclass
class Step:
    """One step of the bench's chain, ready to roll: the check, its time and its rent, and
    `settle(made, margin)`, which changes the world by the craft's own rule and answers
    {"tell", "effects", "made": [names], "mastery": int, "levelled": [...]}. A made step is
    the plain quality unless `quality` says otherwise: a keeper's own roll decides it on a
    commission (rules/commission.py), never the typed line's player."""
    craft: str
    method: str
    label: str
    dc: int
    terms: list
    minutes: int
    settle: Callable[[bool, int], dict]
    rent_cp: int = 0
    rent_to: str | None = None
    final: bool = False
    # Pathfinder Unchained's `pure` raw material: the check is rolled twice and the better
    # kept, as the forge and the alchemy bench roll it (the second die is the engine's).
    roll_twice: bool = False


@dataclass
class Target:
    """What the words asked for, grounded in the craft's catalogue."""
    craft: str
    words: str
    name: str
    data: dict = field(default_factory=dict)


def _spans(words: str) -> list[tuple[str, list[str]]]:
    """Every contiguous run of the words, longest first, with the words left over.

    The item is found as the longest run the craft's own finder knows ("a plain longsword"
    -> "longsword", with "plain" over); the words left over are then asked of the craft's
    catalogue of materials, a closed vocabulary — never of a list of English words."""
    from . import holding

    toks = holding.plain(words).split()
    out = []
    for n in range(len(toks), 0, -1):
        for i in range(len(toks) - n + 1):
            out.append((" ".join(toks[i:i + n]), toks[:i] + toks[i + n:]))
    return out


def _leftover_spans(toks: list[str]) -> list[str]:
    out = []
    for n in range(len(toks), 0, -1):
        for i in range(len(toks) - n + 1):
            out.append(" ".join(toks[i:i + n]))
    return out


def _a(noun: str) -> str:
    noun = str(noun or "").strip()
    return english.a(noun)


def _one(name: str) -> str:
    """One made thing in a tell: "an Iron Dagger", but "Cowhide Panels for Boots" — a
    name that is already a plural takes no article."""
    words = str(name or "").split()
    head = next((w for w in words if w.lower() in ("for", "of")), None)
    if head and words.index(head) > 0:
        noun = words[words.index(head) - 1]
    else:
        noun = words[-1] if words else ""
    plural = noun.lower().endswith("s") and not noun.lower().endswith("ss")
    return name if plural else _a(name)


def _mastery_bits(lines: list[dict]) -> tuple[int, str]:
    total = sum(int(r.get("mp", 0) or 0) for r in lines)
    terms = ", ".join(f"{r['mp']} {r['why']}" for r in lines if int(r.get("mp", 0) or 0))
    return total, terms


def mastery_tell(actor, track_id: str, lines: list[dict], levelled: list[int]) -> str:
    """The step's mastery in the tell's words, as `Engine._op_craft` says it."""
    track = wc.get(track_id)
    total, terms = _mastery_bits(lines)
    bits = []
    if total:
        bits.append(f"{actor.name} gains {total} {track.name} mastery ({terms}).")
    for lvl in sorted(set(int(x) for x in levelled)):
        bits.append(f"{actor.name} is {track.name} {lvl} now.")
    return " ".join(bits)


# --- blacksmithing -------------------------------------------------------------------------

class Blacksmith:
    """The forge's chain for a plain weapon, suit or shield: Smelt (only where ore must
    become bars, and only at a smithy, as the bench says), Forge (bars and fuel into the
    blank or plate of the shape), Assemble (the blank or plate with a haft or fastenings).
    Two rolls from bars; three from ore. Nothing optional: no quench, temper, hone, fold,
    alloy or finish, and Assemble is not aimed at masterwork."""

    track = "blacksmith"

    # --- what is asked for ---------------------------------------------------------------
    def target(self, item: str, actor, words: str = "") -> Target | Refusal:
        from . import blacksmith as bs

        said = " ".join(str(item or words or "").split())
        if not said:
            return Refusal("Name what to forge: a weapon, a suit of armour or a shield off "
                           "the book's lists — a dagger, a longsword, a chain shirt.",
                           "no_item")
        for span, rest in _spans(said):
            info = bs.shape_info(span)
            if info is None:
                continue
            metal_id = ""
            for words_left in _leftover_spans(rest):
                m = bs.metal(bs._by_name(words_left) or words_left.replace(" ", "-"))
                if m is None or m.kind not in bs.METAL_KINDS:
                    continue
                if m.rank > 1:
                    return Refusal(
                        f"{m.name} is {m.tier} metal: {_a(info['name'].lower())} of it is "
                        f"finer work than a plain one. {pointer(self.track)}",
                        "beyond_base")
                metal_id = (bs.metal(m.parent) or m).id if m.kind == "ore" else m.id
                break
            return Target(self.track, said, info["name"],
                          {"info": info, "metal": metal_id})
        if not str(item or "").strip():
            # Nothing named, and nothing on the lists in the words: "I work the forge".
            return Refusal("Name what to forge: a weapon, a suit of armour or a shield off "
                           "the book's lists — a dagger, a longsword, a chain shirt.",
                           "no_item")
        return Refusal(f"{said[:1].upper()}{said[1:]} is not a weapon, armour or shield on "
                       f"the forge's lists. Name one — a dagger, a longsword, a chain shirt "
                       f"— or choose a shape at the forge bench.", "no_item")

    # --- the next step of the chain ------------------------------------------------------
    def next_step(self, engine, actor, target: Target, done: list) -> Step | Refusal | None:
        from . import blacksmith as bs
        from . import goods

        if any(d.get("final") and d.get("made") for d in done):
            return None
        scene = engine.scene
        known = engine.places()
        where = bs.where_here(scene, actor, known)
        if not where.get("smithy") and not where.get("kit"):
            return Refusal("There is no forge here: smithing needs a smithy, or a smith's "
                           "field kit in the pack.", "no_forge")
        progress = actor.track(self.track)
        info, want = target.data["info"], target.data.get("metal") or ""
        shape, gear = info["id"], info["gear"]
        items = bs.rack(actor)
        name = info["name"].lower()

        def plain_metal(p) -> bool:
            if p.rank != 1 or p.material == "" or p.from_leather:
                return False
            if want and p.material != want:
                return False
            return bs.metal(p.material) is not None

        def order(p):
            # The forge's own plain metal first (`blacksmith.MIGRATED_PLAIN` makes a
            # migrated sword's fittings of iron), then the rest of the common metals.
            return (p.material != "iron", p.material, p.key)

        mains = sorted((p for p in items if p.form in bs.PIECE_FORMS and p.work is not None
                        and p.work.shape == shape and plain_metal(p)
                        and not p.work.quench and not p.work.worked and not p.passes
                        and "folded" not in p.traits),
                       key=order)
        if bs.from_base(shape):
            return Refusal(f"{_a(name).capitalize()} is finished from a leatherworker's base "
                           f"with studs or plates: that is fitting work, done at the forge "
                           f"bench.", "beyond_base")
        if mains:
            return self._assemble(engine, actor, progress, where, known, target, mains[0],
                                  items)

        fuels = sorted((p for p in items if p.form == "fuel" and p.rank == 1),
                       key=lambda p: ((bs.metal(p.material) or bs.Metal(id="", name="")).has(
                           "sulfurous"), p.material))
        bars_needed = int(info["bars"])
        bars = sorted((p for p in items if p.form in bs.BAR_FORMS and plain_metal(p)
                       and not p.passes and "folded" not in p.traits), key=order)
        enough = [p for p in bars if p.count >= bars_needed]
        metal_word = (bs.metal(want).name.lower() if want and bs.metal(want) else "metal")
        if enough:
            if not fuels:
                return Refusal(f"Forging {_a(name)} needs fuel for the fire — charcoal, "
                               f"coal or peat — and none is in the pack.", "no_fuel")
            return self._forge(engine, actor, progress, where, known, target, enough[0],
                               fuels[0])

        # Not enough bars: ore becomes bars at a smithy's furnace, never at a field kit.
        ores = sorted((p for p in items if p.form == "ore" and p.rank == 1
                       and (not want or (bs.metal(p.material) and
                                         (bs.metal(bs.metal(p.material).parent)
                                          or bs.metal(p.material)).id == want))),
                      key=lambda p: (p.material != "iron-ore", p.material))
        if ores:
            if not where.get("smithy"):
                return Refusal(f"There is ore in the pack but no bars to forge {_a(name)} "
                               f"from, and ore is smelted in a smithy's furnace, not over a "
                               f"field kit.", "needs_smithy")
            if not fuels:
                return Refusal("Smelting ore needs fuel for the furnace — charcoal, coal "
                               "or peat — and none is in the pack.", "no_fuel")
            have = max((p.count for p in bars), default=0)
            return self._smelt(engine, actor, progress, where, known, target, ores[0],
                               fuels[0], max(1, bars_needed - have))
        have = max((p.count for p in bars), default=0)
        bars_words = f"{bars_needed} bar{'s' if bars_needed != 1 else ''}"
        if have:
            # Measured live 2026-10-28: "There is no metal to forge a chain shirt from (2
            # carried, 3 needed)" — "no metal" beside two bars in the pack.
            return Refusal(f"There is not enough {metal_word} to forge {_a(name)}: it takes "
                           f"{bars_words} of one common metal, and {have} "
                           f"{'is' if have == 1 else 'are'} in the pack — or ore and a "
                           f"smithy to smelt more.", "no_material")
        return Refusal(f"There is no {metal_word} to forge {_a(name)} from: it takes "
                       f"{bars_words} of a common metal, or ore and a smithy to smelt it.",
                       "no_material")

    # --- the three steps ------------------------------------------------------------------
    def _plan(self, engine, actor, progress, where, known, method, slots, batch, shape):
        from . import blacksmith as bs
        from . import goods

        plan = bs.plan_step(actor, progress, method, slots, batch, shape=shape,
                            where=where, masterwork=False)
        if plan.problems:
            return None, Refusal(" ".join(plan.problems), "cannot_craft")
        if plan.need is None:
            return None, Refusal(f"No roll can make DC {plan.dc} with +{plan.bonus}: it "
                                 f"{plan.impossible}.", "beyond_skill")
        rent = bs.rent_cp(engine.scene, where.get("smithy"), plan.minutes, known) \
            if plan.units else 0
        if rent and goods.in_copper(actor.purse) < rent:
            return None, Refusal(f"The smith wants {rent} cp for the hours at the forge, and "
                                 f"{actor.name} carries {goods.in_copper(actor.purse)} cp.",
                                 "cannot_pay")
        return (plan, rent), None

    def _step(self, engine, actor, progress, plan, rent, where, *, final: bool,
              doing: str) -> Step:
        from . import blacksmith as bs

        def settle(made: bool, margin: int, quality: int | None = None) -> dict:
            now = int(engine.scene.clock_minutes or 0)
            if made:
                tier = min(PLAIN_QUALITY if quality is None else int(quality),plan.step_ceiling)
                got = bs.settle_made(actor, progress, plan, tier, plan.consumes,
                                     dice=engine.dice, now=now)
                landed = got["landed"]
                names = [w.name for _k, w, _n in landed]
                what = ", ".join(f"{_one(w.name)}" if n == 1 else f"{n} × {w.name}"
                                 for _k, w, n in landed)
                tell = f"{actor.name} {doing}: {what}, made and in the pack."
                effects = [{"ref": actor.ref, "kind": "made", "craft": self.track,
                            "item": w.name, "stock": key, "count": n, "to": actor.ref,
                            "quality": wc.quality_name(int(w.quality or 0))}
                           for key, w, n in landed]
                lines, levelled = got["lines"], got["levelled"]
                spent = [{"key": p.key, "name": p.name, "count": int(n)}
                         for p, n in plan.consumes]
            else:
                got = bs.settle_miss(actor, progress, plan, -margin)
                names = []
                tell = f"{actor.name} {doing}, and the work is spoiled. {got['said']}"
                effects = []
                lines = list(got["mastery"].get("reasons") or [])
                levelled = list(got["mastery"].get("levelled") or [])
                spent = got["lost"]
            for x in spent:
                effects.append({"ref": actor.ref, "kind": "spent", "craft": self.track,
                                "item": x["name"], "count": int(x["count"]),
                                "from": actor.ref})
            mp, _ = _mastery_bits(lines)
            effects.append({"ref": actor.ref, "kind": "craft", "track": self.track,
                            "method": plan.method, "mp": mp, "levelled": levelled,
                            "success": made})
            told = mastery_tell(actor, self.track, lines, levelled)
            return {"tell": f"{tell} {told}".strip(), "effects": effects, "made": names,
                    "mastery": mp, "levelled": levelled, "final": final}

        return Step(craft=self.track, method=plan.method,
                    label=f"Blacksmithing: {plan.method.title()}", dc=int(plan.dc),
                    terms=list(plan.terms), minutes=int(plan.minutes), settle=settle,
                    rent_cp=int(rent or 0),
                    rent_to=(where.get("smithy") or {}).get("keeper"), final=final,
                    roll_twice=bool(plan.lead is not None and plan.lead.has("pure")))

    def _smelt(self, engine, actor, progress, where, known, target, ore, fuel, units):
        got, refused = self._plan(engine, actor, progress, where, known, "smelt",
                                  {"ore": (ore, 1), "fuel": (fuel, 1)}, units, "")
        if refused:
            return refused
        plan, rent = got
        return self._step(engine, actor, progress, plan, rent, where, final=False,
                          doing=f"smelts {ore.name.lower()} at the furnace")

    def _forge(self, engine, actor, progress, where, known, target, bar, fuel):
        info = target.data["info"]
        got, refused = self._plan(engine, actor, progress, where, known, "forge",
                                  {"metal": (bar, 1), "fuel": (fuel, 1)}, 1, info["id"])
        if refused:
            return refused
        plan, rent = got
        piece = "plate" if info["gear"] != "weapon" else "blank"
        return self._step(engine, actor, progress, plan, rent, where, final=False,
                          doing=f"forges {bar.name.lower()} into the {piece} of "
                                f"{_a(info['name'].lower())}")

    def _assemble(self, engine, actor, progress, where, known, target, main, items):
        from . import blacksmith as bs

        info = target.data["info"]
        gear = info["gear"]
        names = bs.PIECES[gear]
        second = names[1]
        used = {main.key: 1}

        def fits(p) -> bool:
            if p.key == main.key or p.rank != 1 or p.from_leather:
                return False
            if bs.fit_reason("assemble", second, p, gear=gear):
                return False
            return p.count - used.get(p.key, 0) >= 1

        # A plain fitting before a bar, so a suit's fastenings do not eat metal a later
        # forge would want; the forge's own plain metal (iron) before the rest.
        cands = sorted((p for p in items if fits(p)),
                       key=lambda p: (p.form in bs.BAR_FORMS, p.material != "iron",
                                      p.material, p.key))
        if bs.laced(info["id"]):
            return Refusal(f"{_a(info['name'].lower()).capitalize()} is laced with a "
                           f"leatherworker's lacing set: that is fitting work, done at the "
                           f"forge bench.", "beyond_base")
        if not cands:
            what = ("a haft or grip" if gear == "weapon"
                    else "fastenings — buckles or a bar of iron for rivets")
            # Its own code: a keeper on commission supplies a plain fitting from stock
            # when this is all that is missing (rules/commission.py).
            return Refusal(f"Finishing {_a(info['name'].lower())} needs {what}, and none is "
                           f"in the pack.", "no_fitting")
        got, refused = self._plan(engine, actor, progress, where, known, "assemble",
                                  {names[0]: (main, 1), second: (cands[0], 1)}, 1, "")
        if refused:
            return refused
        plan, rent = got
        return self._step(engine, actor, progress, plan, rent, where, final=True,
                          doing=f"assembles {main.name.lower()} with "
                                f"{_a(cands[0].name.lower())}")


# --- herbalism -----------------------------------------------------------------------------

_VERB = {"brew": "brews", "grind": "grinds", "mix": "mixes"}

class Herbalist:
    """The herb bench's base remedies, by its Herbalist 1 methods (content/rules/
    herbal-methods.json): Brew makes the herb's own infusion or decoction (its part decides
    which), Grind makes a powder or a salve base, and Grind then Mix makes a poultice.
    Every other product in the catalogue — tincture, acetum, infused oil, salve, balm,
    cream, a dried or extracted herb, a reduction — comes of a Herbalist 2 method or a
    blend, and is finer work. A line that names no product brews the herb: the plainest
    finished remedy there is ("I brew a tea from the yarrow")."""

    track = "herbalist"
    # Each base product, by the catalogue's own id, and the methods that make it.
    CHAINS = {"infusion": ("brew",), "decoction": ("brew",), "powder": ("grind",),
              "salve-base": ("grind",), "poultice": ("grind", "mix")}

    def _products(self) -> dict[str, str]:
        from . import crafting

        rows = crafting.herbal_rules()["products"]["products"]
        return {str(r.get("name") or k).lower(): k for k, r in rows.items()}

    def target(self, item: str, actor, words: str = "") -> Target | Refusal:
        from . import crafting

        said = " ".join(f"{item or ''} {words or ''}".split())
        products = self._products()
        form = ""
        for span, _rest in _spans(said):
            if span in products:
                form = products[span]
                break
        if form and form not in self.CHAINS:
            name = crafting.product_row(form).get("name", form)
            return Refusal(f"{_a(name.lower()).capitalize()} is finer work than a plain "
                           f"remedy. {pointer(self.track)}", "beyond_base")
        satchel = crafting.satchel(actor)
        raw = [m for m in satchel if not m.crafted and not m.reagent and m.ingredient_id]
        named = []
        low = said.lower()
        for m in raw:
            name = crafting._lead_name(m).lower()
            if name and name in low and m.ingredient_id not in [x.ingredient_id
                                                               for x in named]:
                named.append(m)
        # The longest name wins, so "juniper berry" is not answered with "juniper"
        # (`ingredients.by_name`'s rule).
        named.sort(key=lambda m: -len(crafting._lead_name(m)))
        if named:
            herb = named[0]
        else:
            kinds = list(dict.fromkeys(crafting._lead_name(m) for m in raw))
            if not kinds:
                return Refusal("There are no herbs in the satchel to work.", "no_material")
            if len(kinds) > 1:
                return Refusal(f"Which herb? The satchel holds {', '.join(kinds[:-1])} and "
                               f"{kinds[-1]}: name the one to work.", "which_herb")
            herb = raw[0]
        return Target(self.track, said, crafting._lead_name(herb),
                      {"form": form, "ingredient": herb.ingredient_id})

    def next_step(self, engine, actor, target: Target, done: list) -> Step | Refusal | None:
        from . import crafting

        if any(d.get("final") and d.get("made") for d in done):
            return None
        progress = actor.track(self.track)
        iid, form = target.data["ingredient"], target.data.get("form") or ""
        satchel = crafting.satchel(actor, int(engine.scene.clock_minutes or 0))
        level = int(progress.level or 1)
        chain = self.CHAINS.get(form, ("brew",))
        raw = [m for m in satchel if not m.crafted and m.ingredient_id == iid
               and not crafting.fit_reason(chain[0], m, [], level)]
        if chain == ("grind", "mix"):
            ground = [m for m in satchel if m.crafted and m.state == "ground"
                      and not m.is_base and iid in (m.from_ingredients or [])
                      and not crafting.fit_reason("mix", m, [], level)]
            if ground:
                return self._step(engine, actor, progress, "mix", ground[0], form,
                                  final=True)
            method = "grind"
        else:
            method = chain[0]
        if not raw:
            have = [m for m in satchel if not m.crafted and m.ingredient_id == iid]
            if have:
                why = crafting.fit_reason(method, have[0], [], level)
                return Refusal(f"{target.name} cannot be worked: {why}.", "cannot_craft")
            return Refusal(f"There is no {target.name.lower()} in the satchel.",
                           "no_material")
        return self._step(engine, actor, progress, method, raw[0], form,
                          final=(method != "grind" or chain == ("grind",)))

    def _step(self, engine, actor, progress, method, m, form, *, final: bool):
        from . import crafting

        plan = crafting.plan_step(actor, progress, method, [(m, 1)], 1,
                                  perks=dict(wc.perk_multipliers(progress)))
        if plan.problems:
            return Refusal(" ".join(plan.problems), "cannot_craft")
        if plan.need is None:
            return Refusal(f"No roll can make DC {plan.dc} with +{plan.bonus}: it "
                           f"{plan.impossible}.", "beyond_skill")
        if final and form and plan.form != form:
            got = crafting.product_row(plan.form).get("name", plan.form)
            want = crafting.product_row(form).get("name", form)
            return Refusal(f"{crafting._lead_name(m)} makes {_a(str(got).lower())} by "
                           f"{method}, not {_a(str(want).lower())}.", "cannot_craft")
        name = crafting.product_row(plan.form).get("name", plan.form or "")

        def settle(made: bool, margin: int, quality: int | None = None) -> dict:
            now = int(engine.scene.clock_minutes or 0)
            if made:
                ceiling = wc.ceiling_index(progress)
                tier = min(PLAIN_QUALITY if quality is None else int(quality),ceiling)
                got = crafting.settle_made(actor, progress, plan, tier, plan.consumes,
                                           dice=engine.dice, now=now)
                stock = got["made"]
                tell = (f"{actor.name} {_VERB.get(method, method)} {crafting._lead_name(m).lower()}: "
                        f"{_a(stock.name) if got['count'] == 1 else str(got['count']) + ' × ' + stock.name}"
                        f", made and in the satchel.")
                effects = [{"ref": actor.ref, "kind": "made", "craft": self.track,
                            "item": stock.name, "stock": stock.id, "count": got["count"],
                            "to": actor.ref, "quality": crafting.quality_name(tier)}]
                names = [stock.name]
                lines, levelled = got["lines"], got["levelled"]
                spent = [{"name": x.name, "count": int(n)} for x, n in plan.consumes]
            else:
                got = crafting.settle_miss(actor, progress, plan, -margin)
                names, effects = [], []
                tell = (f"{actor.name} {_VERB.get(method, method)} {crafting._lead_name(m).lower()}, and the "
                        f"work is spoiled. {got['said']}")
                lines = list(got["mastery"].get("reasons") or [])
                levelled = list(got["mastery"].get("levelled") or [])
                spent = got["lost"]
            for x in spent:
                effects.append({"ref": actor.ref, "kind": "spent", "craft": self.track,
                                "item": x["name"], "count": int(x["count"]),
                                "from": actor.ref})
            mp, _ = _mastery_bits(lines)
            effects.append({"ref": actor.ref, "kind": "craft", "track": self.track,
                            "method": method, "mp": mp, "levelled": levelled,
                            "success": made})
            told = mastery_tell(actor, self.track, lines, levelled)
            return {"tell": f"{tell} {told}".strip(), "effects": effects, "made": names,
                    "mastery": mp, "levelled": levelled, "final": final}

        return Step(craft=self.track, method=method,
                    label=f"Herbalism: {plan.name or method.title()}", dc=int(plan.dc),
                    terms=list(plan.terms), minutes=int(plan.minutes), settle=settle,
                    final=final)


# --- alchemy -------------------------------------------------------------------------------

class Alchemist:
    """A book formula the alchemist knows, bottled by the bench's own two steps: a raw
    reagent made into something that pours or sifts — Calcine (a solid to a powder) or
    Dissolve (a solid into a solvent) — and then Bottle, into a vessel whose kind the
    formula's family needs. An intermediate already on the shelf that bottles into the
    formula is bottled at once. Only the book's formulae are plain (the four classics every
    alchemist starts with, and any book formula learned since); a compound of the
    alchemist's own, a catalyst, distilling, filtering or a reaction is the bench's."""

    track = "alchemist"

    def _known(self, actor) -> dict[str, dict]:
        from . import alchemist as al
        from . import formulae

        # Taught the first time the bench opens (`alchemy_views._ensure_starting`); a
        # typed line is the alchemist at work as surely, and the grant is idempotent.
        al.known_starting(actor)
        return {fid: row for fid, row in formulae.all().items()
                if formulae.knows(actor, fid)}

    def target(self, item: str, actor, words: str = "") -> Target | Refusal:
        from . import formulae

        said = " ".join(f"{item or ''} {words or ''}".split())
        known = self._known(actor)
        every = formulae.all()

        def names(row) -> set[str]:
            return {str(row.get("name") or "").lower(),
                    str(row.get("id") or "").replace("-", " ").lower()}

        hit = None
        for span, _rest in _spans(said):
            hit = next((r for r in every.values() if span in names(r)), None)
            if hit is not None:
                break
        if hit is None:
            book = sorted(str(r.get("name")) for r in known.values() if r.get("book"))
            return Refusal("No formula you know is called that. You know "
                           + (", ".join(book[:-1]) + f" and {book[-1]}" if len(book) > 1
                              else (book[0] if book else "none")) + ".", "no_item")
        if hit["id"] not in known:
            return Refusal(f"You do not know the formula for {hit['name']}: a formula is "
                           f"learned at the alchemy bench, read, taught or found by "
                           f"experiment.", "unknown_formula")
        if not hit.get("book"):
            return Refusal(f"{hit['name']} is a compound of your own: it is bottled at "
                           f"{BENCHES[self.track]['name']}, where its mix is chosen.",
                           "beyond_base")
        return Target(self.track, said, str(hit["name"]), {"formula": hit["id"],
                                                           "row": hit})

    def next_step(self, engine, actor, target: Target, done: list) -> Step | Refusal | None:
        from . import alchemist as al
        from . import formulae

        if any(d.get("final") and d.get("made") for d in done):
            return None
        scene = engine.scene
        known_places = engine.places()
        where = al.where_here(scene, actor, known_places)
        if not where.get("lab") and not where.get("kit"):
            return Refusal("There is no alchemy bench here: the work needs a laboratory, "
                           "or an alchemist's field kit in the pack.", "no_bench")
        progress = actor.track(self.track)
        now = int(scene.clock_minutes or 0)
        fid, row = target.data["formula"], target.data["row"]
        shelf = al.shelf(actor, now)
        fam = str(row.get("family") or "")
        vessels = sorted((it for it in shelf if it.rank == 1
                          and not al.fit_reason("bottle", "vessel", it)
                          and (not fam or fam in formulae.vessel_families(it.material))),
                         key=lambda it: it.key)
        if not vessels:
            return Refusal(f"Bottling {row['name'].lower()} needs a vessel of its kind "
                           f"({fam or 'a vial or a flask'}), and none is in the pack.",
                           "no_vessel")
        vessel = vessels[0]

        def plan_of(method, body):
            plan = al.plan_step(actor, progress, method, dict(body), where=where, now=now)
            if not plan.problems:
                rent = al.rent_cp(scene, plan.lab, plan.minutes, known_places) \
                    if plan.units else 0
                if rent and goods.in_copper(actor.purse) < rent:
                    plan.problems.append(f"The laboratory wants {rent} cp for the hours, "
                                         f"and {actor.name} carries "
                                         f"{goods.in_copper(actor.purse)} cp.")
                plan._typed_rent = rent
            return plan

        from . import goods

        # Something on the shelf that already bottles into it: bottle it now.
        first_problem = ""
        for it in shelf:
            if it.record is None or it.rank != 1 or it.key == vessel.key:
                continue
            if al.fit_reason("bottle", "inputs", it):
                continue
            plan = plan_of("bottle", {"inputs": [{"key": it.key, "count": 1}],
                                      "vessel": vessel.key, "formula": fid})
            if not plan.problems and plan.need is not None and plan.can_roll:
                return self._step(engine, actor, progress, plan, where, final=True,
                                  doing=f"bottles {it.name.lower()} into "
                                        f"{_a(vessel.name.lower())}")
            first_problem = first_problem or " ".join(plan.problems)

        # Else a raw reagent made to pour or sift, whose essences the formula needs.
        need = dict(((row.get("requires") or {}).get("essences") or {}))
        solvents = [it for it in shelf if it.rank == 1
                    and not al.fit_reason("dissolve", "solvent", it)]
        raws = sorted((it for it in shelf if it.record is None and it.rank == 1
                       and it.key != vessel.key and it not in solvents
                       and not al.fit_reason("calcine", "inputs", it)),
                      key=lambda it: it.key)
        for it in raws:
            tries = [("calcine", {"inputs": [{"key": it.key, "count": 1}]})]
            tries += [("dissolve", {"inputs": [{"key": it.key, "count": 1}],
                                    "solvent": s.key}) for s in solvents]
            for method, body in tries:
                plan = plan_of(method, body)
                if plan.problems or plan.need is None or not plan.can_roll:
                    first_problem = first_problem or " ".join(plan.problems)
                    continue
                grades = formulae.mix_grades(plan.mix)
                if all(grades.get(e, 0) >= int(g or 1) for e, g in need.items()):
                    verb = "calcines" if method == "calcine" else "dissolves"
                    how = (f"{verb} {it.name.lower()}" if method == "calcine" else
                           f"{verb} {it.name.lower()} in "
                           f"{next(s.name for s in solvents if s.key == body['solvent']).lower()}")
                    return self._step(engine, actor, progress, plan, where, final=False,
                                      doing=how)
        wants = ", ".join(sorted(need)) or "what it is made of"
        return Refusal(f"Nothing in the pack makes {row['name'].lower()}: it needs a "
                       f"reagent carrying {wants}"
                       + (" (and a solvent to dissolve it in, if it does not grind)"
                          if not solvents else "") + ".", "no_material")

    def _step(self, engine, actor, progress, plan, where, *, final: bool, doing: str):
        from . import alchemist as al

        def settle(made: bool, margin: int, quality: int | None = None) -> dict:
            now = int(engine.scene.clock_minutes or 0)
            told_toxic = []
            if plan.toxics:
                # A toxic reagent hurts at the start of the step, whatever the roll (plan
                # §8.4), through the one hazard door.
                for o in al.apply_rule(engine, actor, plan.toxics, kind="toxic"):
                    if getattr(o, "tell", ""):
                        told_toxic.append(str(o.tell))
            if made:
                tier = min(PLAIN_QUALITY if quality is None else int(quality),plan.ceiling)
                got = al.settle_made(actor, progress, plan, tier, plan.consumes,
                                     dice=engine.dice, now=now, where=where)
                bits, effects, names = [], [], []
                for x in got["landed"]:
                    rec = x["record"]
                    name = str(rec.get("name") or "")
                    names.append(name)
                    n = int(rec.get("count") or 1)
                    if x.get("waits"):
                        day = int(x.get("ready_at") or now) // 1440 + 1
                        bits.append(f"{_one(name) if n == 1 else f'{n} × {name}'}, set to "
                                    f"wait In progress until day {day}")
                    else:
                        bits.append(f"{_one(name) if n == 1 else f'{n} × {name}'}, made "
                                    f"and in the pack")
                    effects.append({"ref": actor.ref, "kind": "made", "craft": self.track,
                                    "item": name, "stock": x["key"], "count": n,
                                    "to": actor.ref, "waits": bool(x.get("waits")),
                                    "quality": wc.quality_name(tier)})
                tell = f"{actor.name} {doing}: {'; '.join(bits)}."
                lines, levelled = got["lines"], got["levelled"]
                spent = [{"name": it.name, "count": int(n)} for it, n in plan.consumes]
            else:
                got = al.settle_miss(engine, actor, progress, plan, -margin)
                names, effects = [], []
                tell = f"{actor.name} {doing}, and it fails. {got['said']}"
                lines = list(got["mastery"].get("reasons") or [])
                levelled = list(got["mastery"].get("levelled") or [])
                spent = got["lost"]
            for x in spent:
                effects.append({"ref": actor.ref, "kind": "spent", "craft": self.track,
                                "item": x["name"], "count": int(x["count"]),
                                "from": actor.ref})
            mp, _ = _mastery_bits(lines)
            effects.append({"ref": actor.ref, "kind": "craft", "track": self.track,
                            "method": plan.method, "mp": mp, "levelled": levelled,
                            "success": made})
            told = mastery_tell(actor, self.track, lines, levelled)
            tell = " ".join([*told_toxic, tell, told]).strip()
            return {"tell": tell, "effects": effects, "made": names, "mastery": mp,
                    "levelled": levelled, "final": final}

        return Step(craft=self.track, method=plan.method,
                    label=f"Alchemy: {plan.method.title()}", dc=int(plan.dc),
                    terms=list(plan.terms), minutes=int(plan.minutes), settle=settle,
                    rent_cp=int(getattr(plan, "_typed_rent", 0) or 0),
                    rent_to=(plan.lab or {}).get("keeper") if plan.lab else None,
                    final=final, roll_twice=bool(plan.roll_twice))


# --- leatherworking ------------------------------------------------------------------------

class Leatherworker:
    """The leather bench's chain for plain leather or a plain pattern (rules/leatherworker.py
    `PRODUCTS`), by its Leatherworker 1 methods: Flense (a green or salted hide to a pelt),
    Tan (the pelt with the plainest tannin carried), Cut (the pattern's body from tanned
    leather), Stitch (the panels, with thread) or Harden (a plated pattern's body), and
    Assemble (the body, with fastenings where the pattern has them, cut from the same
    leather when none are carried). A tan that soaks in the pack or a vat goes In progress
    and the chain stops there: typed again once it is collected, it goes on from where the
    work stands. Curry, tooling, dyeing, laminating and masterwork are the bench's."""

    track = "leatherworker"

    def target(self, item: str, actor, words: str = "") -> Target | Refusal:
        from . import leatherworker as lw

        said = " ".join(f"{item or ''} {words or ''}".split())
        names = {}
        for key, row in lw.PRODUCTS.items():
            names[key] = key
            names[str(row.get("word") or "").lower()] = key
        product = ""
        for span, rest in _spans(said):
            if span in names:
                product = names[span]
                break
        # A hide named by the catalogue: a special one (rare and up) is finer work.
        hide = ""
        by_name = {str(m.name).lower(): mid for mid, m in (lw.materials() or {}).items()
                   if getattr(m, "kind", "") == "hide"}
        for span, _rest in _spans(said):
            mid = by_name.get(span) or by_name.get(f"{span} hide", "")
            if mid:
                doc = lw.material(mid) or {}
                if wc.tier_rank(str(doc.get("tier") or "common")) > 1:
                    return Refusal(f"{doc.get('name', mid)} is {doc.get('tier')}: leather of "
                                   f"it is finer work than plain. {pointer(self.track)}",
                                   "beyond_base")
                hide = mid
                break
        name = lw.PRODUCTS[product]["word"] if product else "leather"
        return Target(self.track, said, name, {"product": product, "hide": hide})

    def next_step(self, engine, actor, target: Target, done: list) -> Step | Refusal | None:
        from . import leatherworker as lw

        if any(d.get("final") and d.get("made") for d in done):
            return None
        scene = engine.scene
        known = engine.places()
        where = lw.where_here(scene, actor, known)
        if not where.get("tannery") and not where.get("field_kit"):
            return Refusal("There is no leather bench here: the work needs a tannery, or a "
                           "leatherworker's field kit in the pack.", "no_bench")
        progress = actor.track(self.track)
        now = int(scene.clock_minutes or 0)
        rack = lw.rack(actor, now)
        product, want_hide = target.data.get("product") or "", target.data.get("hide") or ""

        def mine(p) -> bool:
            if p.hide is None or p.old or p.spoiled or p.count <= 0:
                return False
            if want_hide and p.material != want_hide:
                return False
            return p.rank == 1

        def plan_of(method, slots, **kw):
            plan = lw.plan_step(actor, progress, method, slots, 1, where=where,
                                masterwork=False, now=now, **kw)
            return plan

        if product:
            info = lw.PRODUCTS[product]
            plated = info.get("body") == "plate"
            bodies = [p for p in rack if mine(p) and p.hide.pattern == product
                      and (p.hide.part or "body") == "body"]
            ready = [p for p in bodies if (p.form == "plate" if plated else
                                           (p.form == "panel" and "stitch" in p.hide.worked))]
            if ready:
                body = ready[0]
                slots = {"body": (body, 1)}
                if info.get("fastenings"):
                    fast = [p for p in rack if p.key != body.key and p.count > 0
                            and not lw.fit_reason("assemble", "fastenings", p,
                                                  product=product)]
                    if fast:
                        slots["fastenings"] = (sorted(fast, key=lambda p: (p.rank, p.key))[0],
                                               1)
                    else:
                        leather = [p for p in rack if mine(p) and p.form in
                                   ("leather", "fur", "rawhide")]
                        if not leather:
                            return Refusal(f"{info['word']} needs fastenings — a lacing set, "
                                           f"or leather to cut one from — and none is in "
                                           f"the pack.", "no_material")
                        return self._step(engine, actor, progress, where, known, plan_of(
                            "cut", {"hide": (leather[0], 1)}, product="lacing"),
                            final=False, doing=f"cuts a lacing set from "
                                               f"{leather[0].name.lower()}")
                return self._step(engine, actor, progress, where, known,
                                  plan_of("assemble", slots, product=product), final=True,
                                  doing=f"assembles the {info['word'].lower()}")
            panels = [p for p in bodies if p.form == "panel"]
            if panels:
                p = panels[0]
                if plated:
                    return self._step(engine, actor, progress, where, known,
                                      plan_of("harden", {"piece": (p, 1)}), final=False,
                                      doing=f"hardens {p.name.lower()}")
                threads = sorted((t for t in rack if t.count > 0 and not lw.fit_reason(
                    "stitch", "thread", t)), key=lambda t: (t.rank, t.key))
                if not threads:
                    return Refusal(f"Stitching {info['word'].lower()} needs thread, and none "
                                   f"is in the pack.", "no_material")
                return self._step(engine, actor, progress, where, known,
                                  plan_of("stitch", {"piece": (p, 1),
                                                     "thread": (threads[0], 1)}),
                                  final=False, doing=f"stitches {p.name.lower()}")
            leather = [p for p in rack if mine(p) and p.form in ("leather", "fur", "rawhide")]
            if leather:
                return self._step(engine, actor, progress, where, known,
                                  plan_of("cut", {"hide": (leather[0], 1)}, product=product,
                                          part="body"),
                                  final=False, doing=f"cuts the {info['word'].lower()} "
                                                     f"from {leather[0].name.lower()}")
        pelts = [p for p in rack if mine(p) and p.form == "pelt"]
        if pelts:
            p = pelts[0]
            tannins = sorted((t for t in rack if t.count > 0 and not lw.fit_reason(
                "tan", "tannin", t)), key=lambda t: (t.rank, t.key))
            if not tannins:
                return Refusal("Tanning needs a tannin — bark, brains, alum — and none is in "
                               "the pack: without one the pelt only dries to rawhide.",
                               "no_material")
            for t in tannins:
                plan = plan_of("tan", {"hide": (p, 1), "tannin": (t, 1)})
                if not plan.problems:
                    return self._step(engine, actor, progress, where, known, plan,
                                      final=not product, doing=f"tans the pelt with "
                                                               f"{t.name.lower()}")
            return self._step(engine, actor, progress, where, known,
                              plan_of("tan", {"hide": (p, 1), "tannin": (tannins[0], 1)}),
                              final=not product, doing="tans the pelt")
        raw = [p for p in rack if mine(p) and p.form in ("green", "salted")]
        if raw:
            p = raw[0]
            return self._step(engine, actor, progress, where, known,
                              plan_of("flense", {"hide": (p, 1)}), final=False,
                              doing=f"flenses {p.name.lower()}")
        if not product and any(mine(p) and p.form in ("leather", "fur", "rawhide")
                               for p in rack):
            return Refusal("The hides in the pack are tanned already. Name what to make of "
                           "them — leather armour, boots, a belt — or choose a pattern at "
                           "the leather bench.", "no_item")
        what = (f"{target.name.lower()}" if product else "leather")
        return Refusal(f"There is no hide in the pack to make {what} from.", "no_material")

    def _step(self, engine, actor, progress, where, known, plan, *, final: bool,
              doing: str):
        from . import goods
        from . import leatherworker as lw

        if plan.problems:
            return Refusal(" ".join(plan.problems), "cannot_craft")
        if plan.need is None:
            return Refusal(f"No roll can make DC {plan.dc} with +{plan.bonus}: it "
                           f"{plan.impossible}.", "beyond_skill")
        scene = engine.scene
        rent = lw.rent_cp(scene, where, plan.minutes, known) if plan.units else 0
        vat = (lw.vat_rent_cp(scene, where, plan.wait_minutes, plan.vats, known)
               if plan.units and plan.vats else 0)
        if (rent or vat) and goods.in_copper(actor.purse) < rent + vat:
            return Refusal(f"The tanner wants {rent + vat} cp for the yard and the vats, and "
                           f"{actor.name} carries {goods.in_copper(actor.purse)} cp.",
                           "cannot_pay")

        def settle(made: bool, margin: int, quality: int | None = None) -> dict:
            now = int(scene.clock_minutes or 0)
            stop = False
            if made:
                tier = min(PLAIN_QUALITY if quality is None else int(quality),plan.step_ceiling)
                ceiling = max(0, int(plan.step_ceiling))
                got = lw.settle_made(actor, progress, plan, tier, plan.consumes, now=now,
                                     where=where, setup_score=tier / (ceiling + 1),
                                     vat_cp=vat)
                bits, effects, names = [], [], []
                for row in got["landed"]:
                    rec = row.get("record")
                    name = (rec or {}).get("name") or row["hide"].name
                    names.append(name)
                    n = int(row.get("count") or 1)
                    if row.get("waits"):
                        stop = True
                        day = int(row.get("ready_at") or now) // 1440 + 1
                        bits.append(f"{_one(name) if n == 1 else f'{n} × {name}'}, set to "
                                    f"wait In progress until day {day}")
                    else:
                        bits.append(f"{_one(name) if n == 1 else f'{n} × {name}'}, made "
                                    f"and in the pack")
                    effects.append({"ref": actor.ref, "kind": "made", "craft": self.track,
                                    "item": name, "stock": row["key"], "count": n,
                                    "to": actor.ref, "waits": bool(row.get("waits")),
                                    "quality": wc.quality_name(tier)})
                tell = f"{actor.name} {doing}: {'; '.join(bits)}."
                lines, levelled = got["lines"], got["levelled"]
                spent = [{"name": p.name, "count": int(n)} for p, n in plan.consumes]
            else:
                got = lw.settle_miss(actor, progress, plan, -margin)
                names, effects = [], []
                tell = f"{actor.name} {doing}, and the work is spoiled. {got['said']}"
                lines = list(got["mastery"].get("reasons") or [])
                levelled = list(got["mastery"].get("levelled") or [])
                spent = got["lost"]
            for x in spent:
                effects.append({"ref": actor.ref, "kind": "spent", "craft": self.track,
                                "item": x["name"], "count": int(x["count"]),
                                "from": actor.ref})
            mp, _ = _mastery_bits(lines)
            effects.append({"ref": actor.ref, "kind": "craft", "track": self.track,
                            "method": plan.method, "mp": mp, "levelled": levelled,
                            "success": made})
            told = mastery_tell(actor, self.track, lines, levelled)
            return {"tell": f"{tell} {told}".strip(), "effects": effects, "made": names,
                    "mastery": mp, "levelled": levelled, "final": final, "stop": stop}

        return Step(craft=self.track, method=plan.method,
                    label=f"Leatherworking: {plan.method.title()}", dc=int(plan.dc),
                    terms=list(plan.terms), minutes=int(plan.minutes), settle=settle,
                    rent_cp=int(rent or 0),
                    rent_to=(where.get("tannery") or {}).get("keeper")
                    if where.get("tannery") else None, final=final)


# --- enchanting ----------------------------------------------------------------------------

class Enchanter:
    """No plain base item exists at the circle. An enchantment is a property chosen and
    seated essence by essence on a vessel the craft's own rule requires to be masterwork
    or better (`enchanter.vessels`), then bound over days: every part of it is a choice the
    circle asks the player for. So a typed enchanting line is answered with the circle,
    never half-made (the owner's ruling: anything beyond base goes to the bench)."""

    track = "enchanter"

    def target(self, item: str, actor, words: str = "") -> Target | Refusal:
        return Refusal("An enchantment is chosen at the circle — the vessel, the essences "
                       "seated and the property bound — and there is no plain one a few "
                       "words can make.", "at_the_bench")

    def next_step(self, engine, actor, target, done):
        return None


_CRAFTS: dict[str, object] = {"blacksmith": Blacksmith(), "herbalist": Herbalist(),
                              "alchemist": Alchemist(), "leatherworker": Leatherworker(),
                              "enchanter": Enchanter()}


def get(craft: str):
    """The craft's typed-line adapter, or None for a craft with none yet."""
    return _CRAFTS.get(str(craft or "").strip().lower())


def _names_in(craft: str, item: str) -> bool:
    """Whether `item` names a thing in this craft's own catalogue — the forge's shapes, the
    herb bench's products, the known-or-not formulae, the leather patterns — by the same
    finders the chains use. Closed vocabularies, never English."""
    from . import blacksmith as bs

    spans = [s for s, _r in _spans(item)]
    if craft == "blacksmith":
        return any(bs.shape_info(s) for s in spans)
    if craft == "herbalist":
        products = Herbalist()._products()
        return any(s in products for s in spans)
    if craft == "alchemist":
        from . import formulae

        names = {n for r in formulae.all().values()
                 for n in (str(r.get("name") or "").lower(),
                           str(r.get("id") or "").replace("-", " ").lower())}
        return any(s in names for s in spans)
    if craft == "leatherworker":
        from . import leatherworker as lw

        names = set(lw.PRODUCTS) | {str(r.get("word") or "").lower()
                                    for r in lw.PRODUCTS.values()}
        return any(s in names for s in spans)
    return False


def craft_for(craft: str, item: str) -> str:
    """The craft the thing belongs to: the reader's, unless the thing is in exactly one
    OTHER craft's catalogue and not in the reader's own. Measured live 2026-10-28: "I forge
    myself a chain shirt with my field kit" came back `craft: leatherworker`, and the
    leather bench refused a chain shirt it has no pattern for. The reader's closed answer
    is a model's; the catalogues are the engine's (models read, code validates)."""
    # An enchantment's object is a thing that already exists ("I enchant my longsword"): it
    # names the forge's shape and is never a request to forge one.
    if craft == "enchanter" or not str(item or "").strip() or _names_in(craft, item):
        return craft
    owners = [c for c in CRAFTS if c != craft and _names_in(c, item)]
    return owners[0] if len(owners) == 1 else craft
