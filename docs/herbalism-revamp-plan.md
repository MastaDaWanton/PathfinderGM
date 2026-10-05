# Herbalism revamp — the plan

Drafted 2026-10-02 from eight rounds of the owner's answers. The prior-art sweep it leans on
is `docs/herbalism-prior-art.md` (sources and a critic pass are in that file). Nothing here is
built yet. Numbers marked **(proposed)** are my defaults and still need tuning or a ruling;
everything else is the owner's decision as given.

---

## 1. What herbalism is for

Three kinds of fun, in this order:

1. **Hands-on craft (the lead).** The bench is the pleasure. Each tool has weight, sound and
   motion, and the player's own hands decide how good the result is.
2. **Discovery.** Herbs keep their secrets until you taste them, study them, are taught, or read
   about them. A herbarium fills in as you learn.
3. **Apothecary life.** Your remedies matter to people: you can sell them, companions rely on
   them, and people see your work. This part is mostly a **world** system that herbalism plugs
   into (§12), not something the class hands out.

**The boundary with alchemy** (the owner's rule of thumb):

```
[ Herbalism ]  poultices, salves, teas        ->  physical healing, the body
      |  the turning point: adding supernatural catalysts, or ones that alter form
[ Alchemy ]    potions, transmutation         ->  magical / supernatural utility
```

Hybrid ingredients such as Basilisk Eye, Phoenix Feather and Shadowvine appear on **both**
benches. The herbalist can use one only for an effect that works **on or in the body**: an eye
salve that lets you see the unseen, or a draught swallowed for an immunity. An effect that
reaches **outside** the body, such as invisibility, stays alchemy's (§5.2).

---

## 2. The owner's decisions (2026-10-02)

| Area | Decision |
|---|---|
| Minigame role | The d20 Craft check (the player's own dice) decides success. The minigame only climbs the quality tier. |
| Repetition | **Always play it.** Bulk crafting is allowed, and the minigame result applies to the whole stack. That is the risk. |
| Bulk risk | One tier for the whole stack, and **world time grows with batch size**. |
| Scope | The bench and progression. Foraging stays as it is, apart from the knowledge and mastery hooks. |
| Discovery | You learn properties by tasting, by a study check, from people, and from libraries and manuals. |
| Quality ladder | Crude, Sound, Fine, Superior, Flawless, then Flawless +1, +2 and so on. |
| Quality does | Stronger and longer, softens drawbacks, worth more. |
| Chains | Step by step. Each method is its own roll and minigame, and its intermediate lands back on the shelf. |
| Minigames | **One per method.** |
| Methods removed | Distill, Preserve, Purify, Refine, Catalyst crafting. |
| Method added | **Dry**: 2 of a thing make 1 dried thing at ×1.5 potency and ×1.5 duration. |
| Concentration | "You should be able to concentrate almost anything over and over as long as you have two of it." |
| Products | Infusion (tea, an end product), Decoction, Tincture, Acetum, Poultice, Salve, Balm, Cream. **Infused oil** is an intermediate you can sell, used to make salves, balms and creams. |
| Bases | Grinding bark or tree sap makes a salve base, and so does beeswax (with others to come). Mix makes the bases, and you mix oils into a base to add effects. |
| Oils | Dry the herb, then add it to oil to make infused oil, at a cost of 1 oil each. |
| Product strength | The **ingredient is the base stat**. Each method multiplies it, and a tincture multiplies more than an infusion. An infusion of a very potent concentrate can therefore beat a tincture of a weak herb. |
| Products differ by | Shelf life, how it is taken, strength, and which effects it can carry. |
| Levels | **Level 1:** grind, mix, brew. **Level 2:** all the other methods except Neutralize. **Level 3:** legendary material and Neutralize. |
| Rarity | Level 1 opens common and uncommon, level 2 rare and exotic, level 3 legendary. |
| Neutralize | Costs specific materials, tagged as **neutralizers**. |
| Endless levels | After level 3 the levels never stop. Each one, you **pick two** perks (the same one twice is allowed) from potency, duration, quality and extra-yield chance. |
| Quality vs level | Your level **raises the ceiling**. The minigame decides where you land under it. |
| Controls | Mouse, keyboard, and a **Steady mode** for accessibility. |
| Game time | Each step costs world time, and the time grows with batch size. |
| Failed roll | The PF1e Craft rule: fail by 4 or less and you lose the time but keep the materials. Fail by 5 or more and **half** the materials are ruined. |
| Tasting | **Real risk.** It costs the dose, applies the raw effect for real, and reveals **1 positive and 1 negative** trait (if the herb has a negative one). The safer routes are to take the herb to someone who knows, or to look it up in a library. |
| Mastery | Each craft, a quality bonus, firsts, foraging, and **reading unread herbalism manuals**. |
| Herbarium | Shown on hover at the bench, and as a full section in the Journal. |
| Recipes | Loading a recipe sets up the bench; you **still play** the minigame. |
| Old saves | **Convert.** Levels above 3 become endless levels with perks picked on first load. Old stock stays usable and sellable, but the removed methods cannot make more. |
| Apothecary | "None of this should come automatically with the class." Reputation and renown are a world system for every kind of deed; herbalism only gives it **a way to be seen**. Keep commissions to a minimum unless you run a store or stall. |
| Tools | **3D tools** (three.js, like the dice) with the flat UI kept. |
| Sound | **App-wide** sound system, with the bench as one part. |
| Feedback | **Big and juicy**, but never block a menu for more than a second. |
| Mood | **Wild forager's camp**: a fold-out kit, with the backdrop being wherever you stand. |

---

## 3. What the research changes

These findings are from `docs/herbalism-prior-art.md`.

- **Start the minigames generous.** Stardew's creator says fishing "starts too hard" and that
  the bar should have started bigger. Potion Craft added *Auto Hold* because holding the mouse
  to grind and stir tired players' hands, and that is exactly our grind input. **Applied here:**
  no game needs a long press. Every hold has a toggle form, so Steady mode swaps holds for
  presses (the Xbox accessibility guideline 107 pattern; The Long Dark turns every hold into a
  single press).
- **Agency beats dice for quality.** WoW replaced *Inspiration*, a random chance of higher
  quality, with *Concentration*, a resource the player chooses to spend. Blizzard's reason was
  "a lack of decision making and agency for the crafter". Our quality is skill, not luck, which
  matches. The extra-yield perk is the one random reward, so its roll is shown.
- **Everyone else added a way out of repetition; we deliberately do not.** The owner chose
  "always play". KCD2 removed KCD1's auto-brew and players modded it back. We take that risk on
  purpose and soften it three ways:
  1. bulk crafting (one game per stack);
  2. recipe loading (§9.6);
  3. short games, 4–8 seconds each **(proposed)**.

  **Watch it in playtest:** if the bench starts to feel like a chore, this is the first decision
  to revisit.
- **Never take ingredients on a minigame miss after the roll succeeded.** A miss lowers quality
  only. Materials are lost only to the d20, under the book rule.
- **Never use colour alone** (Game Accessibility Guidelines). Every dimmed ingredient says *why*
  in words. Every zone has a shape or edge as well as a colour, and a dry bundle's state is
  shown by its shape as well as its colour.
- **Honour `prefers-reduced-motion`** (WCAG 2.3.3). Big and juicy is the default. Under reduced
  motion, screen shake and confetti are dropped and the result card still lands.
- **The tabletop base.** In PF1e Ultimate Wilderness herbalism, each herb names its own
  preparation (leechwort is dried and ground). That is our `part` and `prep` tags in §5.1. Raw
  herbs spoil in a day and prepared ones in a month, which is where §7's shelf lives come from.
  The Angry GM's advice also applies: keep ingredient descriptors to a few (rarity, type, one
  special quality), never pages of charts.

---

## 4. Progression

### 4.1 Levels 1–3

| Level | Opens | Materials | Tools on the bench |
|---|---|---|---|
| 1 | **Grind, Mix, Brew** → Infusion, Decoction, Poultice, salve bases | common, uncommon | mortar and pestle, bowl and paddle, camp pot |
| 2 | **Dry, Reduce, Extract, Infuse (oil), Steep** → Infused oil, Salve, Balm, Cream, Tincture, Acetum, field harvesting of monster parts | rare, exotic | drying rack, knives and tongs, oil crock, steeping jars |
| 3 | **Neutralize**, and legendary material | legendary | thick gloves, dropper, neutralizer reagents |

Mastery thresholds: 25 to reach level 2 and 65 to reach level 3 (unchanged from today).

**Removed from the Herbalist:** distill, preserve, purify, refine and catalyst crafting, along
with the level 4 and 5 rows, the `legendary-catalyst` milestone and its deed. The Alchemist
class already has its own verbs (calcine through catalyze), so nothing is moved across to it.
`tests/test_legendary_catalyst.py` is retired, and its defects are re-pinned against the new
level 3 gate.

### 4.2 Endless levels (4 and up)

`Track.to_next` already allows a track with no ceiling (`rules/worldclass.py` `_advance`, "No
ceiling"). Each level after 3 lets you **pick two** perks from the list below, and you can take
the same one twice.

| Perk | Per pick **(proposed)** |
|---|---|
| Potency | +5% to the potency multiplier on everything you make |
| Duration | +10% to duration |
| Quality | +1 to the quality **ceiling** (Flawless, then Flawless +1, and so on) |
| Yield | +5% chance per craft of one extra dose. The engine rolls this and shows the roll. |

- **Threshold curve (proposed):** 50 + 10 × (level − 3) mastery per endless level. It is gentle
  on purpose, because the perks are small.
- **Where you pick:** a perk-picker card in the Herbalist panel. Points that have not been
  picked stay banked. Nothing is auto-picked, except during migration (§14), and even then the
  player chooses on their first load.
- **How perks are stored:** perks are documents read live, like feats (stage 8's rule: never a
  stored `ActiveEffect` per perk). `Progress` gains `perks: {"potency": n, ...}`, and the bench
  reads it.

### 4.3 The quality ceiling

| Your standing | Ceiling |
|---|---|
| Level 1 | Fine |
| Level 2 | Superior |
| Level 3 | Flawless |
| Each Quality perk | +1 (Flawless +1, +2, …) |

The minigame's score scales to *your* ceiling: a perfect run lands exactly on it, and the bands
below are spread evenly under it. A level 1 herbalist with perfect hands makes Fine work. A
master with eight Quality perks needs a near-perfect run to reach Flawless +8.

### 4.4 Mastery sources

| Source | Award **(proposed)** | Notes |
|---|---|---|
| Each successful step | 1, +1 per rarity band above common | Replaces "first time 3 / repeat 1". Steps now count one at a time, so the old per-stage award is gone. |
| Quality bonus | +1 at Superior, +2 at Flawless or higher | This is what lets your hands speed you up. |
| Firsts | +3 for each: first time you learn a property, make a product type, or work a new herb | Repeatable across the whole herbarium, so discovery keeps paying. |
| Foraging and harvesting | unchanged | As it works today. |
| Reading an unread herbalism manual | +5, once per manual | See §8.4. |

**Superseded 2026-10-05 for successes:** the owner ruled "batch of 10 should pay 10", so
every successful step pays and `REPEAT_LIMIT` no longer caps one (rules/worldclass.py).
As first planned: keep `REPEAT_LIMIT` (3) and `MISHAP_LIMIT` (2), since they are the anti-grind rule, but key
them on (method, ingredient) instead of the old recipe id. Drop `TRIVIAL_GAP`: the levels no
longer climb in rarity bands past level 3, so "beneath you" has no meaning in the endless
levels.

---

## 5. Ingredients: the base stat

### 5.1 New ingredient fields

All of these default so that an old file still loads (the same rule as `herbprep.Prep`).

| Field | Values | Why |
|---|---|---|
| `part` | leaf, flower, root, bark, berry, seed, sap, resin, fungus, gland, organ, bone, horn, feather… | Brew turns leaf and flower into an **Infusion**, and root, bark and berry into a **Decoction**. Bark and sap grind into **salve base**. |
| `base_for` | `["salve"]` … | The things that thicken a salve, balm or cream: beeswax, ground bark, ground sap or resin, and later others. |
| `neutralizer` | strength, e.g. `1` | Neutralize consumes one of these per dose. Candidates include lime, charcoal, milk of magnesia, and clay. They are probably alchemist materials too, so they appear on both shelves. |
| `solvent` | `oil`, `alcohol`, `vinegar`, `water` | Infuse needs 1 oil per dose, and Steep needs alcohol (Tincture) or vinegar (Acetum). Water is always on hand at a camp. |
| per-effect `route` | `ingest`, `skin`, `eyes`, `wound`, `inhale`, `external` | See §5.2. |
| `hybrid` | true | The ingredient appears on both the herbalist and the alchemist shelves. |

The ingredient file has 161 entries:

| Kind | Common | Uncommon | Rare | Exotic | Legendary |
|---|---|---|---|---|---|
| herb | 104 | 16 | 7 | 4 | 1 |
| monster part | — | 4 | 6 | 7 | 3 |
| fungus | 5 | 1 | — | — | — |
| poison | — | — | 3 | — | — |

150 of them already have structured effects. Tagging `part`, `route` and the rest is a batch
job through the existing `tools/export_herbs_for_tagging.py` and
`docs/herb-tagging-prompt.md` pipeline. It is model-assisted, every row is validated
mechanically (enums, at least one route per effect), and **the owner reviews the hybrid rows by
hand**, because the body-versus-external line is a judgment call.

**World Bible** (fixes are world-agnostic): a world's own herbs need the same fields. Add `part`,
`route`, `base_for`, `neutralizer` and `solvent` to `docs/campaign-format.md` as optional
fields with defaults, and list them in `docs/from-world-bible.md` as what the next export should
carry.

### 5.2 Body versus external: the hybrid rule

Every effect carries a `route`. The herbalist's bench can carry an effect only when its route is
one of `ingest`, `skin`, `eyes`, `wound` or `inhale`. An `external` effect, one that changes what
others see or that reaches past the skin (invisibility, flight, illumination cast on the world,
charm another person), shows up on the herbalist's shelf card as "alchemy only". It is still
**dropped** from a herbal product, never silently kept.

For example, Gloomwraith Tendril is "see invisible creatures" with route `eyes`, so an
herbalist can make it as an eye cream. Mistveil Fern, partial incorporeality, is route
`external`, so the herbalist cannot.

The test for this pins a ratchet: a herbal product never carries an `external` effect, checked
by set comparison against the product's effect specs.

### 5.3 Concentration

This is the owner's rule: concentrate almost anything over and over as long as you have two of
it.

- **Solids: Dry.** 2 → 1 at ×1.5 potency and ×1.5 duration, and you can repeat it on what you've
  dried. Dried herbs are what Infuse needs.
- **Liquids: Reduce** (Q1, settled). This is a liquid's own concentration step: it simmers two
  doses down to one at ×1.5, it is opened at Level 2, and it has its own minigame (§9). Without
  it a tincture could never be concentrated, and the owner's "almost anything" says it should
  be.
- **The old ×2 Concentrate** (`crafting.CONCENTRATE_*`, two doses to one at twice the potency
  and one rarity band up) is **retired** in favour of Dry and Reduce at ×1.5. Its rarity step is
  kept: each concentration moves the result one band rarer. That keeps the ladder gated by level
  (you can't hold legendary-band concentrate before level 3), and the 2ⁿ dose cost is the
  natural brake.
- **Nothing is capped (owner, 2026-10-02, Q2).** "Concentration should be harder and harder,
  so that the only way to get to an extreme concentration is to have extra levels in
  herbalism." Potency, bonuses, durations and healing all scale without a ceiling. Depth is
  gated by the check instead:
  - **The DC climbs faster with every step.** Concentration step *n* adds 2*n* to the
    product's DC, so the total added is *n*(*n*+1): +2, +6, +12, +20, +30, +42…
    **(proposed curve)**.
  - **A natural 20 does not succeed automatically on a bench check.** This is the CRB's rule
    for skill checks: the natural 1 and 20 rule covers attacks and saves, not skills. Today
    the bench treats a 20 as a success (`play/craft_views.py:609` and `:1327`, and `_chance`
    clamps the shown odds to 5–95). Under that, anyone with enough doses reaches any depth by
    luck, and the gate is gone. Once DC − bonus is over 20, the step is impossible, and the
    bench says so in words ("needs +N more to the check") instead of offering a 0% roll.
  - **Levels are the way through.** Each endless level adds +1 to the check through the
    existing `Herbalist N` term (`crafting.check_terms`), on top of the perks.

  A worked example: a level-10 character with Wisdom +4 at Herbalist 3 has a check bonus of
  +12. On a common herb (DC 10) that bonus covers:

  | Step | DC | Odds |
  |---|---|---|
  | 3 | 22 | 10+ on the d20 |
  | 4 | 30 | 18+ on the d20 |
  | 5 | 40 | impossible: needs Herbalist 11 |
  | 6 | 52 | needs about Herbalist 23 |

  Each step also costs twice the doses of the last and runs the book's failure rule, so a miss
  by 5 or more ruins half of a large stack. Extreme concentrate is a master's work, and it is
  rare.
- The minigame is **not** made harder per step. The owner chose "quality only", and the d20
  is the gate.

---

## 6. Methods

Each method is one bench session: drop ingredients, see the time cost, roll the d20, play the
minigame, and the result lands on the shelf. The per-method potency and duration multipliers
live in a rule-row file, `content/rules/herbal-methods.json`, never in code.

| Method | Level | Takes | Makes | Potency / duration **(proposed)** | World time per dose **(proposed)** |
|---|---|---|---|---|---|
| Grind | 1 | any grindable solid | powder; bark, sap or resin become **salve base** | ×1.1 / ×1.0 | 10 min |
| Mix | 1 | 2+ prepared things | a **Poultice** (ground fresh herb and a binder such as water, bran or moss), a **salve base** blend, or **Salve / Balm / Cream** from a base and infused oil | the weighted mean of its parts | 10 min |
| Brew | 1 | leaf or flower in water, or root, bark or berry in water | **Infusion** (end product) or **Decoction** (end product) | ×1.0 / ×1.0, or ×1.25 / ×1.25 | 30 min, or 2 h |
| Dry | 2 | 2 of a solid | 1 dried | ×1.5 / ×1.5 | 8 h (sun or fire) |
| Extract | 2 | a part in a shell, gland or pod | the usable part | ×1.0 (but botches lose potency) | 30 min |
| Infuse (oil) | 2 | dried herb and **1 oil** | **Infused oil** (sellable intermediate) | ×1.25 / ×1.5 | 4 h |
| Steep | 2 | herb and **alcohol**, or herb and **vinegar** | **Tincture** or **Acetum** | ×1.5 / ×2.0, or ×1.25 / ×1.75 | sets up in 10 min, then ready in **2 weeks** (tincture) or **1 week** (acetum) |
| Neutralize | 3 | a volatile thing and 1 **neutralizer** | the safe thing | ×0.9 (the cost of safety) | 20 min |
| Reduce | 2 | 2 of a liquid | 1 | ×1.5 / ×1.5 | 1 h |

**Steeping happens in the world.** Steep makes a sealed jar that sits on the shelf as
"steeping, ready on day N". It is an object in your gear (the gear and load rules apply), and
you can carry it. Time passes through the ordinary clock, and the jar's tincture appears when
the day comes. This is the first bench product with a timer. It uses the same freshness clock
`herbprep` already keeps, read the other way round.

**Order rules carried over from `herbprep`:**
- Extraction comes first.
- A volatile ingredient must be neutralized before it is ground. Neutralize opens at level 3,
  so the lock stays until then (Q3, settled). Teachers, shops and alchemists sell
  **pre-neutralized** stock earlier: the same ingredient in the `neutralised` state, priced
  above the raw one.
- Brew finishes a liquid.
- Mix finishes a topical.

**Bulk.** One roll and one minigame cover the whole stack, and the stack shares one tier. The
world time is per dose × batch size **(proposed: no discount)**. Missing the d20 by 5 or more
ruins half the stack's materials, rounded up.

---

## 7. Products

The potency of a product is: the ingredient's own potency × each method's multiplier × the
quality multiplier × the perks.

| Product | How it's taken | Action to use **(proposed)** | Keeps **(proposed)** | Can carry routes | Notes |
|---|---|---|---|---|---|
| Infusion | drunk | standard action | 1 day | ingest, inhale (steam) | gentle; the level 1 workhorse |
| Decoction | drunk | standard action | 3 days | ingest | stronger; from hard parts |
| Tincture | drops on the tongue | move action | 1 year | ingest | concentrated; keeps |
| Acetum | drunk, or rubbed on | move or standard | 6 months | ingest, skin | cheaper solvent |
| Poultice | bound on a wound | full-round action; works on the unconscious | 1 day | wound, skin | fresh only |
| Infused oil | not used directly; sold or mixed | — | 1 month | — | intermediate |
| Salve | rubbed on | standard action; works on the unconscious | 1 month | skin, wound, eyes | the base and oil staple |
| Balm | rubbed on | standard action | 6 months | skin | firmer and more wax; long duration (weather, cold) |
| Cream | rubbed on | move action | 1 week | skin, eyes | light; fast; spoils sooner |

Who can use what follows the routes. An unconscious ally can take a poultice or salve but not
a tea. An immunity that must be swallowed needs a liquid. A sight effect needs a salve or cream.
The narrator is told this through tells, never through mechanics prose (law 3).

Existing products such as old teas, tinctures and distillates map onto these names during
migration (§14).

---

## 8. Discovery and the herbarium

### 8.1 Knowledge

A new store on the character: `known: {ingredient_id: {"effects": [indices],
"drawbacks": [indices], "how": [...]}}`. Unknown properties stay hidden everywhere:
- on the bench card;
- in the herbarium;
- in the shelf hover;
- in the narrator's brief.

**The narrator never learns an unknown property** (law 3: tells only). Making a product
reveals every effect the product actually carries, as in Skyrim's alchemy (see the research
file).

**What a new herbalist starts knowing (Q4, settled):** the common herbs native to their
homeland's biomes, recorded with how = "homeland". Starting with nothing would make level 1 a
lottery of poison.

### 8.2 Tasting

A new engine op, `taste` (the gate and applicator belong to the engine; the model never authors
it). It works like this:
- It costs one dose.
- It applies the herb's **raw** effects for real through `ActiveEffect`, with origin
  `item:<id>`, through the mind gate and every other existing door. A nibble of hemlock
  paralyses you.
- It reveals **one positive** trait and **one negative** trait, if the herb has one. It prefers
  traits you don't know yet, so tasting a second time teaches you something new.

The tell names what you felt. The narrator voices it.

### 8.3 Study

A bench action and a sheet action: a Knowledge (nature) or Profession (herbalist) roll, on the
player's dice.
- **DC (proposed):** 10 + 5 per rarity band.
- **Success** reveals one unknown property, and one more for every 5 points above the DC.
- It takes 10 minutes and **does not** cost the dose.
- A miss teaches nothing and can be retried after a rest, as in PF1e's take-the-time convention.

### 8.4 People and books

- **Teachers.** Anyone whose occupation is herbalist, healer, hedge-witch or the like (from
  `content/people/occupations.json`) can identify a herb you show them or teach you a property.
  They are paid in coin or a herb, and gated by attitude the same way confiding is
  (`rules/confiding.py`). A friendly healer tells you more. Nothing is automatic: you have to
  ask.
- **Libraries.** A town place of kind library or scriptorium, or a temple's archive, lets you
  look a herb up for a fee and an hour's time. It reveals what the world knows (the herb's
  common properties), never its rare secrets.
- **Manuals.** A new item kind: herbalism manuals, such as "A Hedge-Wife's Almanac". Each lists
  a set of herbs and properties. Reading one takes hours, teaches those properties, and pays
  **+5 mastery once** (unread → read is recorded per manual). They are sold in markets and
  found as loot.

### 8.5 The herbarium

- **Bench:** hovering a shelf ingredient shows what you know, with dashes for the gaps and how
  you learned it ("tasted, Day 14").
- **Journal:** a Herbarium section beside History. It lists every herb you've met, grouped by
  kind. Each entry has a sketch slot (a plate when we have art), the biomes you found it in, and
  its known properties, with "—" for the gaps. This is the collection screen that makes
  discovery feel like progress.

---

## 9. The bench: flow and minigames

**The full interface design is in `docs/herbalism-ui-plan.md`** (2026-10-02). It covers:
- a stage-first layout that opens over the table;
- engraved game-icons.net icons;
- the old bench kept for the other crafts.

Where the UI plan is more specific than this section, the UI plan wins.

### 9.1 The flow (the owner's example, adapted)

```
┌ Ingredients ───────┬ The bench ─────────────────────────┬ Result ───────────────┐
│ the shelf, filtered │ [Grind][Mix][Brew][Dry][Extract]…  │ what's forming        │
│ by the active       │                                    │ (Poultice of Comfrey) │
│ method:             │   3D tool on the forager's kit,    │                       │
│ • fits: lifted,     │   backdrop = where you stand       │ quality ladder, live: │
│   soft glow         │                                    │ Crude Sound Fine ▲    │
│ • doesn't: dimmed + │   drop zone ─ time cost: 2h 30m    │ Superior Flawless     │
│   the reason in     │   [ Roll Craft d20 ]               │ ceiling marked        │
│   words             │   ── minigame strip (after roll) ──│ potency · duration    │
│ • locked: padlock + │                                    │ keeps · how it's taken│
│   "Herbalist 2"     │                                    │ [Recipe ▾] batch [5]  │
└─────────────────────┴────────────────────────────────────┴───────────────────────┘
```

1. **Pick a method.** The previous tool leaves, the new one drops onto the kit with a weighty
   landing, and the shelf re-filters at once (eligible items lift, the rest dim, each dimmed one
   with its reason in words).
2. **Drop.** Validation reuses `herbprep.can` and `crafting.prep_problem`, so the reasons the
   page already gives are kept. An ingredient that fits plays its drop (a heavy clunk into stone,
   a hiss into oil). Once something fits, the time cost and the **Roll** button appear.
3. **Roll.** The d20 is the player's own dice: the same `dice3d` throw and the 0.2.3 verdict word
   (brass 3D SUCCESS or FAILURE). On a failure the book rule applies (§6), and the bench says
   plainly what was lost.
4. **Play the minigame.** It slides up under the tool and lasts 4–8 seconds. The result card's
   ladder climbs live as you play.
5. **Land the result.** The product or intermediate flies to the shelf. Mastery is itemised (the
   existing award breakdown), and any first-time discovery gets its own line.

### 9.2 Shared minigame frame

Every game is a module with the same contract: `start(tuning) → score 0..1`. The page sends the
score; **the server turns it into a tier** against the character's ceiling (§4.3). The client
never names a tier (the same shape as "no model authors a number": the player supplies the
skill and the engine does the arithmetic). Each game has three inputs:

- **mouse**: click, drag and short presses, never a long hold;
- **keyboard**: Space plus the arrow keys;
- **Steady mode** (a setting): slower drift, a wider window, every hold turned into a toggle, and
  rapid tapping turned into a rhythm at half speed. It keeps the game but makes it physically
  easy.

**Tuning:** generous to begin with, and the same for every level (the owner chose "quality
only", so skill doesn't widen the zone; the ceiling is what grows). Difficulty comes from the
ingredient: a root is harder to grind than a leaf, and a volatile one is twitchier to
neutralize.

### 9.3 The games

| Method | Tool (3D) | Game | Mouse | Keyboard | Good / bad looks like |
|---|---|---|---|---|---|
| **Grind** | stone mortar and pestle | **Crush rhythm.** A ring shrinks toward the pestle's strike mark; strike as it closes. Six to eight beats; hard parts (root, bark) have a slower, heavier tempo. | click | Space | each hit sends crunch and dust as the powder gets finer; a miss scatters grit and the powder stays coarse |
| **Mix** | wooden bowl and paddle | **Fold the pattern.** Trace the shown stroke (circle, figure-eight, fold) before the base sets; the texture meter smooths as you follow it. | drag along the guide | arrow keys in the shown order | glossy, even sheen; or lumpy and split |
| **Brew** | blackened camp pot over a fire | **Keep the simmer.** A heat needle drifts and you feed or bank the fire to keep it in the zone. For an Infusion the zone sits low (don't boil away the oils); for a Decoction it sits high and lasts longer. | click to feed, release to bank | ↑ / ↓ | a steady curl of steam and clear colour; or a rolling boil, scum and cloudiness |
| **Dry** | rack of hanging bundles over smoke | **Turn the bundles.** Three to five bundles cure at different speeds; turn each as it reaches the band. The band is shown by **shape** (the leaves curl) and colour. | click the bundle | 1–5 keys | crisp, even colour; too soon stays damp, too late is brittle and scorched |
| **Extract** | knife, tongs, and the part on a board | **The clean cut.** Follow the incision path at an even pace and stop at the nodes. Going too fast nicks the gland and loses potency. | drag along the path | hold → to advance, release at nodes (toggle in Steady mode) | an intact gland lifted whole; or a ruptured sac |
| **Infuse (oil)** | clay oil crock in warm ashes | **Low and slow.** Keep the heat between the *cold* line and the *scorch* line while the infusion bar fills. A gentler, longer zone than Brew. | click to add embers | ↑ / ↓ | golden oil with herbs suspended; or smoke and darkening |
| **Steep** | glass jar, bottle of spirit or vinegar | **Pour to the line.** Pour the solvent and stop at the mark for this herb's ratio, then seal it with a twist on the beat. | press to pour, release to stop | Space | a clean seal and the right ratio; or a weak or overfull jar |
| **Neutralize** | dropper, gloves, reagent | **Titrate.** A volatility needle swings; each drop of neutralizer calms it, but past centre it weakens the material. Stop with the needle settled in the safe band. Each dose uses a neutralizer. | click per drop | Space per drop | a calm, stable needle and safe handling; or too few drops (a sting) or too many (potency lost) |
| **Reduce** | small pan | **Don't scorch it.** Keep the simmer high while the level drops, and pull it off at the line. | click and release | ↑ / ↓ / Space | a thick, dark reduction; or a burnt crust |

Each game is about 6 seconds **(proposed)**. Bulk does not lengthen the game (the owner chose
time, not difficulty, as the bulk cost).

### 9.4 Big and juicy, never in the way

- **Per hit:** particles, a camera nudge, a crunch or hiss, and a glow when you move up a tier.
- **Flawless:** the 3D brass word from the d20 verdict, gilt sparks, and a short screen shake.
- **Rule: no flourish holds a menu for more than one second.** Every flourish can be clicked
  through and runs on its own layer with `pointer-events: none`. The shelf and the method buttons
  stay live throughout. A test measures this.
- **Reduced motion:** no shake, no confetti, and a simple fade on the ladder. Sounds still play.

### 9.5 The forager's camp

The kit unfolds on whatever you're standing on. The backdrop is chosen from the scene's
`biome` (forest floor, swamp hummock, snow, desert rock, tavern table, road) and from whether
you are indoors (`places.roofed`). The lighting matches the time of day from the clock.

### 9.6 Recipes

The existing **Save recipe** button stays. Loading a recipe walks the bench through its first
method with the ingredients pre-dropped. You still roll and still play, and after each step the
next one is offered.

---

## 10. 3D and assets

- **Renderer.** Reuse the three.js setup that `play/static/js/dice3d.js` already ships, giving
  one scene per tool with simple physics for drops (a short tween with a settle, not a physics
  engine).
- **Models (Q5, settled).** The vessels are low-poly and built in code (lathe a mortar, extrude
  a rack). The props come from CC0 packs (Kenney, Quaternius, Poly Haven). Every asset's licence
  is recorded in `docs/asset-licences.md`; the bestiary licensing question shows why that needs
  writing down.
- **Budget.** The installer is 119.7 MB. Keep the tools to 5 MB or less together, using glTF
  with Draco compression.

---

## 11. Sound: app-wide

The app makes no sound today. This adds a small sound system for the whole app; the bench is
its first big user.

- **Engine.** Web Audio, with one `AudioContext`, buses (UI, dice, bench, ambience, combat,
  verdict) and a master bus. Settings get a volume slider per bus and a mute, saved with the
  other settings. It works the same in the packaged Electron app (allow autoplay after the first
  click, the browser rule).
- **Bank.** About 40 sounds to begin with. On the bench: per-method sounds (stone crunch,
  stirring, simmer, the crackle of turning bundles, the knife, the oil hiss, a pour and seal,
  a drip) plus success and failure stings. Elsewhere: dice rattle and land, page turns, doors,
  coins, combat hits and misses, the arrival of a Continue.
- **Variation.** Two to four takes per sound, with ±5% pitch randomization so repeats don't
  sound copy-pasted.
- **Licensing:** CC0 or owned, recorded in `docs/asset-licences.md` (Q5).
- **Ambience:** a quiet bed per biome under the camp (wind, insects, rain).

---

## 12. Apothecary life: herbalism's way to be seen

Herbalism gets **nothing automatic**. It emits **deeds** that a separate, world-wide
**renown** system (its own plan, not part of this one) can pick up:

- **Seen work.** Healing someone with a remedy in front of witnesses, or curing a named NPC.
  This uses the seen-people and witness machinery the scene already has. Nobody knows unless
  someone sees it or you tell them.
- **Told.** Saying "I'm a herbalist" to someone records that they know.
- **Sold.** Every sale at a shop or stall records the buyer and the quality. A Flawless remedy
  sold in town is a fact the town can talk about.

**Commissions:** none, unless you run a store or stall. Then the renown system can send buyers
with requests. That depends on property and stalls, which don't exist yet (the workbench
`fixed_tools` note from 2026-08-25 still holds).

**Selling now:** `rules/pricing.py` multiplies a product's price by its quality **(proposed:
×0.5 Crude, ×1 Sound, ×1.5 Fine, ×2 Superior, ×3 Flawless, +×0.5 for each step above)**.

**The party relies on you**, through systems that already exist:
- a hurt or sick companion can ask for a remedy you carry (the interjection door from 0.2.3);
- companions react to Crude versus Flawless work in their own manner;
- treating the party with your products at camp speeds healing through the camp rules.

---

## 13. How it obeys the three laws

- **Tags.** Quality is `quality.<tier>` on the product record. The `route` values are an
  enumerated vocabulary. Volatility stays a `Prep` flag. Nothing matches strings.
- **One applicator.** Tasting, drinking and applying all go through `ActiveEffect` with origin
  `item:<id>`. Quality, potency and perks multiply the effect spec inside the engine before it is
  applied. The modifier funnel is untouched.
- **Severed tells.** The narrator learns of a remedy only from its tell ("a Fine comfrey
  poultice; the bleeding stops"). Unknown properties never reach the brief.
- **No model authors a number.** The minigame score comes from the player, and the server
  converts it to a tier. Every rate lives in rule rows: `herbal-methods.json`,
  `herbal-products.json`, `quality.json` and `herbal-perks.json`.
- **Grep every copy when a rule changes.** The removed methods also live in:
  - `rules/crafting.py` (`POTENCY`, `CLEANSING`, `FINISHING`);
  - `rules/herbprep.py` (preserve);
  - `content/world-classes/herbalist.json`;
  - `docs/alchemy.md`;
  - `gm/judgement.py` and `gm/interpret.py` (craft words);
  - `gm/prompts.py`;
  - `play/templates/play/craft.html`;
  - `play/craft_views.py`;
  - `rules/benches.py`;
  - the manual;
  - `tests/test_crafting.py` (99 hits) and `tests/test_legendary_catalyst.py`.

  The first lane's job is a full list of every copy.

---

## 14. Migrating old saves

On first load, a version-stamped migration (`herbalism_v2`) runs once per character.

1. **Levels 4 and 5 become endless levels.** Herbalist 4 becomes level 3 plus one perk pick
   (two perks); Herbalist 5 becomes level 3 plus two picks. Banked mastery carries over. The
   picker opens on the first visit to the bench, and nothing is spent until the player chooses.
2. **Stock.** Distilled, refined, purified or preserved items stay usable and sellable under
   their old names, marked "an old method". Their effects are kept as they are.
3. **Recipes** that use a removed method are kept but flagged "needs a new method". Loading one
   explains which step no longer exists.
4. **Knowledge.** A converted herbalist knows every property of every herb they have already
   crafted with, which is fair, since they used them.
5. **Proof.** Run the migration against the owner's real save (read-only copy in the scratchpad,
   as before) and against Bobby. Round-trip the result through save and load.

---

## 15. Build order (lanes)

| # | Lane | Contents | Depends on |
|---|---|---|---|
| 0 | **Rules ruling** | Done 2026-10-02 (§16) | — |
| 1 | **Data** | Ingredient fields (§5.1) and the tagging pass, owner review of the hybrid rows, the four rule-row files, manuals as items, neutralizers and solvents as materials, the World Bible contract | 0 |
| 2 | **Engine** | The new method set, products, Dry/Reduce, bases and oils, steeping jars on the clock, neutralizer cost, quality from score, bulk and the book's failure rule, time cost, endless levels and perks, the mastery sources, migration | 1 |
| 3 | **Discovery** | The `known` store, the `taste` op, study, teachers, libraries, manuals, the narrator gate, the Journal herbarium | 1 (parallel with 2) |
| 4 | **Bench flow (flat)** | The method strip, shelf filtering with reasons, the roll, the minigame frame, the result card and ladder, recipes, batch, the perk picker | 2 |
| 5 | **Minigames** | Nine games (grind, mix, brew, dry, extract, infuse, steep, neutralize, reduce) on the shared frame with mouse, keyboard and Steady mode | 4 |
| 6 | **3D tools and camp** | One tool per method, biome backdrops, juice, reduced motion | 4 (parallel with 5) |
| 7 | **Sound** | The app-wide engine and settings, then bench sounds, then the rest of the app | can start any time |
| 8 | **World hooks** | Deeds emitted for renown, sale records, companion requests, prices by quality | 2 |
| 9 | **Proof** | The full suite, the live app on scratch data, the packaged build | all |

### 15.1 Tests each lane must add

Each test's docstring names the defect it prevents.

- **A herbal product never carries an `external` effect** (set comparison against the specs).
- **A minigame miss after a successful roll never takes materials.** From the research: no
  surviving game punishes twice.
- **Missing the d20 by 4 or less keeps every material; by 5 or more ruins exactly half,
  rounded up, across a bulk stack.**
- **A tier above the ceiling is impossible.** The server clamps the score to the ceiling, so a
  forged score of 1.0 at level 1 is Fine.
- **No flourish holds the shelf or method buttons for more than 1000 ms.** Measured in the live
  page.
- **Every dimmed ingredient has a reason in words.** Colour alone fails the Game Accessibility
  Guidelines.
- **Tasting applies the raw drawback through `ActiveEffect`, and reveals at most one positive
  and one negative trait.**
- **An unknown property never reaches the narrator's brief.** Grep the brief for each hidden
  effect.
- **Migration from Herbalist 5 keeps every banked point and every stock item.** Run against the
  owner's save copy.
- **Concentration depth is gated by the check, not by luck.** A natural 20 on a step whose DC
  is beyond 20 + bonus does not succeed, and the bench names the shortfall. Without this, under
  the bench's old natural-20 rule, any depth was reachable with enough doses.
- **The concentration DC rises by 2*n* at step *n*,** and the shown odds match the roll.
- **A tincture is not ready before its day.** Advance the clock by 13 days, then 14.
- **Steady mode has no hold longer than one press** for any game.

---

## 16. The owner's answers to the open questions (2026-10-02)

All six are settled. The owner set Q2 themselves and accepted my recommendation for the rest
("everything else sounds great").

| # | Question | Answer |
|---|---|---|
| Q1 | Do liquids concentrate too? | **Yes, through Reduce**: two doses become one at ×1.5, Level 2, with its own minigame. Reduce is in the method list (§6) and the minigames (§9.3). |
| Q2 | Should flat bonuses be capped? | **Cap nothing.** Each concentration step is harder than the last, so extreme depth needs endless levels (§5.3). |
| Q3 | Volatile materials need Neutralize (Level 3) before grinding. | **Keep the lock.** Teachers, shops and alchemists can sell **pre-neutralized** stock before then. That stock is an ingredient in the `neutralised` state, priced above the raw one. |
| Q4 | What does a new herbalist already know? | **The common herbs of their homeland's biomes**, recorded in `known` with how = "homeland". |
| Q5 | Where do the 3D tools and sounds come from? | **Vessels built procedurally in code, with CC0 props and sounds.** Every licence goes in `docs/asset-licences.md`. |
| Q6 | Is steeping real world time? | **Yes.** A tincture takes 2 weeks and an acetum 1 week. The jar travels with you and is ready on its day. |

The owner also accepted the **(proposed)** numbers as starting values, chiefly:
- the per-method multipliers in §6;
- the product rows in §7;
- the perk sizes and threshold curve in §4.2;
- the mastery awards in §4.4;
- the concentration DC curve in §5.3;
- the price ladder in §12.

All of them live in rule rows so they can be tuned in play without a code change.
