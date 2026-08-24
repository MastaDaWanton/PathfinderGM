# Enchanting

*The Enchanter world class: what it is, what it works with, and how a binding is made.*

Herbalism reads what a leaf already is. Enchanting imposes a structure that was not
there: an essence — a pinch of captured flame, the film a haunting leaves on flagstones,
grief from somewhere better than here — is chalked into a circle, channelled through a
gemstone, and fixed permanently into an item good enough to hold it. The output is not a
jar that is drunk once. **A finished enchantment is a standing effect list on an item**:
permanent `rules/effectspec.py` specs, plus whatever the material costs its bearer,
because enchanting's materials have temperaments and some of them charge rent.

The craft runs on the same machinery as herbalism on purpose. The track is a JSON file
through `rules/worldclass.py` unchanged; the chain rules (`rules/enchanter.py`) mirror
`rules/crafting.py`'s names and contract — ordered methods, validation into readable
`problems` **before** anything is rolled, homebrew layered over shipped. Costs round
down, benefits round up, as everywhere.

## Two modes, one bench

Enchanting has **two tabs**, and they are different crafts wearing one track.

| | **The circle** (`rules/enchanter.py`) | **The book** (`rules/magicitem.py`) |
|---|---|---|
| What it is | The house craft: essences, foci, chalk on a floor | Pathfinder's own Craft Magic Arms and Armor / Craft Wondrous Item |
| What you spend | Essences, gems, ink, chalk — things you go and find | Gold and time, at the book's rates |
| The ladder | Essence tiers, common to legendary | +1 to +5, plus named properties as bonus equivalents |
| The check | d20 + Enchanter + ½ level + Int vs 10 + 5×tier | The same roll, vs **5 + caster level** |
| Its own risk | A mishap cracks the focus | None: patient workshop work, nothing explodes |
| Prerequisite | The materials, and the hour | The prerequisite **spell** — known, or held in a potion |

Both end in the same place: a standing effect list on an item, `Result.output` in the
same shape, `craft: "enchanter"` on both, and the same three-term check. A player who
switches tabs does not find their bonus quietly changing.

---

## The track

| Level | Tools | New methods | Max tier | The work |
|---|---|---|---|---|
| 1 | chalk and a quiet room | attune, scribe, **bind, seal** | common | The whole ritual in miniature: a mote bound into a quartz. |
| 2 | inscription set, jeweller's loupe | focus, channel | uncommon | Proper gem anchoring. Slick leathers, shadowed cloaks. |
| 3 | attunement circle *(fixed)* | imbue | rare | More than one essence per working. Flaming blades begin here. |
| 4 | binding braziers, silvered bell | empower | exotic | Raising a binding one band beyond its essence. |
| 5 | enchanter's sanctum *(fixed)* | awaken | legendary | Dancing blades, vorpal edges, items with a voice. |

**Bind and seal are level 1, and that is a load-bearing decision.** The first draft
gated bind at level 3 — the "dangerous heart" placed mid-track — and that recreated the
exact deadlock the herbalist's `_deeds_note` records: with no completable craft below 3,
no mastery could ever be earned to *reach* 3. The heart of the craft is learned first in
its smallest form; the danger scales with the tier ceiling, not with withholding the
verb. What level 3 actually adds is **imbue** — the right to put a second essence in the
same working — which is where compound items and mishaps worth the name both start.

**The level-5 deed is binding a legendary essence**, and the ladder to it is **empower**:
an Enchanter 4 who empowers an exotic working (+5 DC) produces a legendary-tier result,
and that success is the deed. Same shape as the herbalist reaching legendary through the
concentration ladder, and for the same reason — a deed that requires the level it gates
can never be earned.

### The methods

| Method | Level | What it does |
|---|---|---|
| attune | 1 | Reads the essence and the vessel: what the material wants, what it will refuse. Every ritual opens with it. |
| scribe | 1 | Chalks and inks the circle and the vessel's sigils. Consumes the ink and circle materials. |
| bind | 1 | Fixes channelled essence to the vessel. The dangerous step; a mishap here is what cracks foci. |
| seal | 1 | Closes the working. Always last — an unsealed binding bleeds away by morning, and nothing follows a seal. |
| focus | 2 | Sets the gemstone as the binding's anchor. |
| channel | 2 | Draws the essence through the circle into the focus without grounding it out through the enchanter. |
| imbue | 3 | Lets more than one essence share one working — as many as the focus holds, one per family, always. |
| empower | 4 | Raises a binding one tier band beyond its essence, at +5 DC. The ladder to legendary work. |
| awaken | 5 | The sanctum ritual for legendary and intelligent work. |

### The refusals

Every one is a sentence on the preview, raised before any roll — a chain the character
cannot make never advances the track:

- Essence with no `bind` in the chain: *"Essence goes nowhere without binding."*
- `bind` with no focus material: *"Binding needs a focus: the essence has nowhere to
  live, and a circle alone cannot hold it."*
- A focus too small — by top rank or by total ranks: *"A quartz cannot hold a storm."*
- `seal` before `bind`, or `bind` without `seal`.
- A non-masterwork vessel (the book's own gate) — and an item nobody has vouched for
  counts as non-masterwork, because assuming it would wave every rusty sword through.
- Two essences of one family: the seat is taken. Checked by family, not id, so
  Arcane Essence III over Arcane Essence I is refused too — the ladder is re-enchanted,
  never stacked.
- Two essences without `imbue` — a restriction that lifts itself at level 3, exactly as
  herbalism's infusion rule does.
- A night-binding material by daylight, when the scene has a clock to ask.

### The check and the DC

**d20 + Enchanter level + half character level + Intelligence** against
**DC 10 + 5 × essence rank + 5 per essence beyond the first**, plus +5 per off-type
binding (a fire mote pressed into armour), +5 for empower, minus what catalysts give
(powdered pearl −2, adamantine dust −3). Herbalism rolls Wisdom because it reads what is
already there; enchanting rolls Intelligence because it imposes what is not.

**Mishap**: the essence is spent either way — it went into the circle. An ordinary focus
is scorched and survives. A *fragile* focus (the diamond) cracks through and is **lost,
not spent** — a successful working returns every focus to the pouch; only the mishap
takes the fragile one. The preview says which fate applies before the player chooses the
stone.

---

## The materials

117 entries in `content/materials/enchanter-materials.json`, across all five tiers.
Homebrew materials in the user's `homebrew/materials/` directory layer over the shipped
set entry by entry — a new essence just works, and a homebrew copy of a shipped id merges
over it field by field.

### Essences (the big group)

An essence carries a **family** — the effect family it can bind — and one vessel takes
one essence per family, ever. Materials have temperaments:

- **Motes** (common): fire, frost, spark, stone, gale, tide, glow, hearth-ember. The
  practice materials. Most carry a `prefers` — fire motes want weapons and resist armour
  at +5 DC; stone motes the reverse.
- **The enhancement ladder**: Arcane Essence I–V (weapons: +N enhancement to attack and
  damage) and Warding Essence I–V (armour: +N enhancement to AC), common through
  legendary, one rung per tier. One family, so a vessel holds exactly one rung.
- **Ghost residue** (rare) only binds at night — under the sun the working finds nothing
  in the phial. Its refinements (ghost touch, etherealness) keep the habit. Moonlit
  varnish, a rare treatment, lifts it.
- **Shadowstuff** (uncommon) grants +5 Stealth and *dims its bearer*: −2 Perception,
  permanent, riding in the finished item's effect list as a marked drawback. The refined
  shadow essences cost more and dim nobody.
- **Dragon ichor** (exotic) binds by colour and only its colour: red fire, blue
  electricity, white cold, green and black acid. Each gives a 1d6 rider plus resistance 5
  in kind.
- **Celestial tears and angel feather** refuse a wielder of evil deeds — the binding
  goes quiet in an unworthy hand. That is the material's own judgement, prose in `text`,
  never a guessed save: what the effect vocabulary cannot express stays narrative.
- **Vicious essence** bites the hand: +2d6 on a hit, 1d6 to the wielder, the drawback a
  real `damage` spec.

### Foci

The focus gates how much essence a binding holds. `capacity` is one number doing two
jobs: the highest essence rank it anchors *and* the total ranks it holds.

| Focus | Tier | Capacity | Character |
|---|---|---|---|
| Quartz | common | 1 | One mote, no more. Survives mishaps with a new flaw and a story. |
| Moonstone | common | 1 | Night materials sit calmer against it. |
| Amethyst | uncommon | 2 | An uncommon essence, or a pair of motes. |
| Sapphire | rare | 3 | The journeyman stone: a flaming binding lives here. |
| Ruby | exotic | 4 | Warm in a cold room once something is bound. |
| Black opal | exotic | 4 | A ruby's equal with a reputation. |
| Diamond | legendary | 5 | Holds anything — and cracks through on a mishap. Lost, not spent. |

### Inks, circle materials, catalysts, treatments

All consumed by the working, success or failure. Inks by tier: silver → octopus-and-iron
gall → quicksilver → auric → phoenix-quill (the quill burns at the last stroke; one
working per quill). Chalks and salts: white chalk → consecrated → bone (ghost and shadow
essences fight a bone circle less) → void chalk → a poured diamond-dust line, which is
why legendary work is priced the way it is. Catalysts lower the DC (−2 to −3). Treatments
prepare the vessel: etching acid bites the sigils into the metal, warding oil sends a
mishap through the circle instead of the hands, moonlit varnish carries its own midnight.

### Vessels

The book's gate, recorded as material entries with a `requires` field: *only a masterwork
item takes an enchantment*. A masterwork weapon or armour from the smith, a masterwork
cloak or hide from the leatherworker, ring and wand and amulet blanks from the jeweller.
This is the cross-craft handoff — the smith's and leatherworker's masterwork outputs are
the enchanter's raw material.

---

## The named properties

Each of the book's named properties exists as an essence + focus + methods combination.
The book's rules are quoted in each entry's `text`; the mechanics are effectspecs where
the vocabulary reaches, and honestly narrative where it does not (threat ranges,
percentage negation, action economy — a guessed spec would be a fact nobody wrote).

| Property | Essence | Tier | Minimum focus | Methods | Mechanics |
|---|---|---|---|---|---|
| +1…+5 weapon | Arcane Essence I–V | common…legendary | quartz…diamond | attune, scribe, focus*, channel*, bind, seal | +N enhancement, attack and damage (specs) |
| +1…+5 armour | Warding Essence I–V | common…legendary | quartz…diamond | as above | +N enhancement AC (spec) |
| Flaming / Frost / Shock / Corrosive | matching essence | rare | sapphire | attune, scribe, focus, channel, bind, seal | +1d6 energy rider (spec) |
| Flaming burst / Icy burst / Shocking burst | burst essence | exotic | ruby | as above | +1d6 rider spec; +1d10 on crit spec, noted |
| Merciful | merciful essence | uncommon | amethyst | as above | +1d6 nonlethal (spec); all-nonlethal narrative |
| Vicious | vicious essence | uncommon | amethyst | as above | +2d6 spec; 1d6 to wielder as drawback spec |
| Keen | keen essence | rare | sapphire | as above | narrative (threat range is outside the vocabulary) |
| Bane | bane essence | rare | sapphire | as above | +2 attack spec and +2d6 spec, noted "against the designated foe" |
| Holy / Unholy / Anarchic / Axiomatic | matching essence | exotic | ruby | as above | +2d6 spec noted vs alignment; negative level as narrative drawback |
| Wounding | wounding essence | exotic | ruby | as above | bleed 1 (spec) |
| Ghost touch | ghost touch essence | exotic | ruby | night, or moonlit varnish | narrative |
| Defending | defending essence | exotic | ruby | as above | narrative (a per-round choice) |
| Speed / Dancing / Vorpal / Brilliant energy | matching essence | legendary | diamond | + awaken, in the sanctum | narrative |
| Slick / Shadow (± improved, greater) | matching essence | uncommon/rare/exotic | amethyst/sapphire/ruby | as above | +5/+10/+15 competence skill spec |
| Fortification light/moderate/heavy | fortification essence | rare/exotic/legendary | sapphire/ruby/diamond | as above | narrative (percentage negation) |
| Energy resistance (± improved, greater) | warding essence by energy | rare/exotic/legendary | sapphire/ruby/diamond | as above | resistance 10/20/30 (spec) |
| Spell resistance | spell resistance essence | exotic | ruby | as above | narrative (SR 15) |
| Invulnerability | invulnerability essence | legendary | diamond | + awaken | DR 5/magic (spec) |
| Etherealness | etherealness essence | legendary | diamond | night + awaken | narrative |

\* focus and channel are level-2 methods; a level-1 working carries the focus as a
material and makes do with attune, scribe, bind, seal.

---

## Worked examples

### A +1 longsword, start to finish

Kesst, Enchanter 1, Int +2, character level 4. On the bench: a **masterwork longsword**
(commissioned from the smith — the ordinary one was refused with the masterwork
sentence), **Arcane Essence I** (common, enhancement family), a **quartz focus**
(capacity 1, exactly enough), **silver ink**, **white chalk**.

Chain: `attune → scribe → bind → seal`. Preview: no problems. DC 15 (10 + 5×1). Bonus +5
(Enchanter 1, half level +2, Int +2) — 55%. Mishap line: the essence is spent, the
quartz is scorched but survives. On a success: **Longsword +1**, standing effects
`combat_mod +1 enhancement attack` and `combat_mod +1 enhancement damage`, both
permanent, both marked `from: Arcane Essence I`. Spent: the essence, the ink, the chalk.
The quartz goes back in the pouch.

### A flaming burst blade

Enchanter 4, at the attunement circle. Masterwork falchion, **Flaming Burst Essence**
(exotic, fire family), **ruby focus** (capacity 4), auric ink, void chalk, and a
**dragon scale catalyst** burnt at the channelling.

Chain: `attune → scribe → focus → channel → bind → seal`. One essence, so no imbue
needed. DC: 10 + 5×4 − 3 = **27**. The effects on success: the 1d6 fire rider on every
hit, the 1d10 on a confirmed critical (noted), both specs. Adding Arcane Essence III to
the same working — a *+3 flaming burst* — is legal at level 4 with `imbue` in the chain:
two essences (enhancement + fire, different families), 4 + 3 = 7 ranks... which exceeds
the ruby's capacity of 4. *A larger stone, or a smaller ambition*: this is diamond work,
and the diamond is the stake on the table if the roll fails.

### Winter-wolf cloak and frost essence (cross-craft)

The leatherworker delivers a **masterwork winter wolf cloak** — their masterwork output
is the enchanter's vessel, recorded here as the `masterwork-cloak-vessel` entry. The
enchanter, level 3, brings **Frost Warding Essence** (rare, cold family, prefers
armour — the pelt half-wants the binding already), a **sapphire focus**, quicksilver
ink, bone chalk.

Chain: `attune → scribe → focus → channel → bind → seal`, DC 25, no off-type surcharge
(the cloak counts as armour, which is what the essence wants). Result: a cloak with
standing `resistance: cold 10`. The GM colour that a winter wolf pelt takes frost
workings a shade easier is exactly that — colour, noted in the vessel entry's text, not
a number the engine applies.

### Something legendary: the storm-heart blade

Enchanter 5, in the sanctum. Masterwork greatsword; **Storm Heart** (legendary — the
storm that names the quartz refusal); **diamond focus**, the only stone that holds it;
phoenix-quill ink; a poured diamond-dust line.

Chain: `attune → scribe → focus → channel → bind → awaken → seal`. DC 10 + 5×5 = **35**.
The mishap line matters here: on a failure the storm is spent *and the diamond cracks
through — lost outright*. On success: a blade with a permanent 2d6 electricity rider,
and a name. An Enchanter 4 can reach this tier the other way — `empower` over an exotic
working, +5 DC — and that success is the level-5 deed, `legendary-binding`.

---

## The second mode: the book

`rules/magicitem.py`, `MODE_ID = "magic-item"`, catalogue in
`content/materials/magic-items.json` — 170 entries: 26 weapon properties, 32 armour and
shield properties, 112 wondrous and slot items.

### The +1 system

Enhancement runs **+1 to +5**. Named properties are priced as **bonus equivalents** and
added on top: flaming +1, frost +1, shock +1, keen +1, bane +1, holy +2, wounding +2,
speed +3, dancing +4, vorpal +5. Three rules govern them, and each refuses with the
arithmetic spelled out:

1. **At least +1 before any property.** Properties are priced on top of an enhancement
   bonus, so there has to be one to be on top of. A flaming sword that is not at least
   +1 cannot be priced at all.
2. **Enhancement never past +5.** The budget above that goes on properties.
3. **Enhancement + properties never past +10.** A +5 vorpal sword is exactly the whole
   budget; anything else added to it is refused.

**Price** is the square of the total bonus: N² × 2,000 gp for weapons, N² × 1,000 gp for
armour and shields. The squaring is the entire reason a high-end item is a campaign goal
rather than a shopping trip — a +1 flaming sword is a *+2 item*, 8,000 gp, not 4,000.
Crafting costs **half** the market price (rounded down, as costs do) and takes **8 hours
per 1,000 gp** (rounded up to whole thousands, because time is a cost too, and a 400 gp
trinket still takes a working day). The check is **DC 5 + caster level**.

### Vessels, and the masterwork asymmetry

Weapons and armour **must be masterwork** — the book's own gate, and an item nobody has
vouched for counts as not masterwork, because assuming it would wave every rusty sword
through. **Jewelry and wondrous items require no masterwork vessel.** That asymmetry is
the book's, not an oversight: a ring blank is a ring blank, and Craft Wondrous Item never
asks a crafter to commission a masterwork one. It is stated here, encoded in
`magicitem.VESSEL_RULES`, and pinned by a test, so nobody "fixes" it later.

Wondrous items are made **whole** — a ring is not a property laid over an enhancement
bonus, and a working that mixes the two would be priced on two tables at once. Slots come
from `rules/tables.py SLOTS`; a slotless item carries `slot: None`.

### House rule 1 — a potion stands in for knowing the spell

The book requires the item's creator to know the prerequisite spell. **In a solo game
that does not gate power, it deletes the feature**: the party is one person, and a
fighter who wants a flaming sword can never qualify, no matter how much gold or time
they have.

So: **a potion holding that spell, consumed in the making, stands in for knowing it.**
The alchemist track brews them; the contract is `holds_spell` (a spell id) and
`caster_level` on the stock entry, and this mode reads only those two fields. Knowing the
spell still works, through `rules/casting.knows`, read-only, and costs nothing.

The refusal names the spell and both routes out, because a refusal that only says "you
cannot" sends the player to a rulebook they do not have:

> Keen needs Keen Edge, and you neither know it nor carry a potion holding it. Brew or
> buy a potion of Keen Edge and it will be consumed in the making.

Every prerequisite spell in the catalogue is a real id in `content/spells` — grounded and
tested, because a misspelled one would refuse a working for a spell no potion could ever
hold.

### House rule 2 — permanency is not required

Several book prerequisites read "…and *permanency*", which is a service bought from a
5th-level caster. A solo campaign cannot farm one. **Dropped outright** rather than
fudged, and every working says so in its notes, so the house rule is visible at the bench
and not only in this file.

### Worked example: a +1 flaming longsword, the book's way

Masterwork longsword from the smith. Enhancement +1, one property (flaming, +1) — total
bonus **+2**. Market price 2² × 2,000 = **8,000 gp**; crafting cost **4,000 gp**; time
**64 hours**. Flaming's caster level is 10, so **DC 15**. The prerequisite is *flame
blade*: a wizard who knows it pays nothing extra, anyone else consumes a potion of it.
Output: a `Flaming Longsword +1`, masterwork, with the +1 enhancement on attack and
damage and the 1d6 fire rider, all validated specs.

---

## Getting the materials

The play page's craft-action button is the hub for **obtaining** materials, and it
replaces the foraging panel that used to sit inside the crafting menu. Every material
says where it comes from, because "where does a fire mote actually come from" is the
question that turns a shelf into a place.

| `obtain` | Count | What it means | Examples |
|---|---|---|---|
| `gathered` | 11 | Skimmed where the world runs thin; `biomes` narrows it | Fire mote (mountain, underground, urban), ghost residue (ruins, underground, swamp) |
| `mined` | 9 | Dug rough and cut at the bench; `biomes` narrows it | Every focus; white chalk from coastal cliffs |
| `harvested` | 18 | Cut from something that recently objected; `from_creature` narrows it | Dragon ichor by colour, lich dust, phoenix quill, angel feather |
| `bought` | 79 | An errand, with a `price_gp` | Inks, chalks, catalysts, vessels, the guild's refined essences |

`rules/enchanter.ACQUISITION` declares five excursions the play layer can wire — skim
essence, mine and cut foci, harvest from the slain, buy inks and catalysts, commission a
vessel — each with the obtain kind it uses and what it needs (a biome, a creature, a
market). `obtainable(kind, biome=…, creature=…)` answers what a given excursion turns up:
a fire mote is not in a bog, and dragon ichor does not come off a rat.

## Icons and tooltips

`rules/enchanter.KIND_GLYPH`, one per material kind, none of them herbalism's 🌿🍄🦴☠️:

| Kind | ✨ essence | 💎 focus | 🖋️ ink | 🜏 chalk | ⭐ salt | 🔮 vessel | 📿 catalyst | 🧿 treatment |
|---|---|---|---|---|---|---|---|---|

Catalyst was a candle (🕯️) until the five tracks were loaded together and
`benches.glyphs()` showed the leatherworker's `wax` on the same glyph — a candle being
the more literal thing for wax to be, the catalyst moved. The clash was invisible from
inside one craft's file, which is why the assertion belongs in the spine.

`rules/magicitem.KIND_GLYPH` covers the second mode's three: 🪄 weapon property,
🧿 armour property, 📿 wondrous. Two of those appear in the essence map as well — the
reserved pool is ten glyphs and enchanting has eleven kinds across its two tabs. Reuse
*within* one craft is legible (🧿 is a warded thing in both places, 📿 a strung-together
working); reuse across two crafts would make one shelf look like another, and does not
happen.

`content/world-classes/enchanter.json` carries `method_help`, one entry per method beside
`method_descriptions` (a test asserts the two sets match — a method that gains a tooltip
and loses its description is a bench that explains half of itself). Each has three
fields, because the tooltip has three jobs: **does** (the mechanical effect in numbers —
DC change, tier step, capacity), **needs** (what must be in the circle for it to be
legal), **for** (what a player reaches for it to accomplish). The magic-item mode has no
ritual stations — the book's making is one long patient session, not a chain of verbs —
so `magicitem.STATIONS` is empty *explicitly*, since an empty dict and a forgotten one
look identical from outside.

---

## Integration notes

*What this slice wanted from shared code and deliberately did not touch — for whoever
wires the bench.*

1. **Attaching a standing enchantment to an inventory item — still the one real gap.**
   `rules/sheet.py` carries weapons as plain strings and consumables as `Stock` dicts; a
   finished enchantment needs a third shape, an item entry with a permanent `specs`
   list. Both modes now emit exactly that as `Result.output`, in the contract shape:
   `id, name, kind: "crafted", craft: "enchanter", tier, rank, count, effects[str],
   specs[validated], from_materials[ids], masterwork, wearable, usable, how[], slot,
   weapon, armour, enhancement, properties[str]`. Nothing needs re-deriving; it needs a
   home on the actor and a summing pass wherever buffs are totalled. The drawback specs
   (marked `drawback: true`, and also listed separately in `Result.drawbacks`) must ride
   along, or shadowstuff stops costing and vicious stops biting.

2. **Bench UI, two tabs.** The crafting page's shape transfers whole for the circle
   mode: materials shelf (grey a material the chain would refuse, via the same problems
   list), method chips in order, the preview card with DC/terms/chance — plus the
   **mishap line**, shown before the roll, because which focus to risk is a player
   choice and `Result.mishap` already writes the sentence. The scene must supply
   `at_night` (the world clock exists for foraging) and the item's masterwork fact. The
   book mode's tab is a different form: a vessel picker, a +N stepper capped at 5, a
   property list filtered by `magicitem.properties_for(vessel_kind)`, and a running
   total-bonus/price/hours readout — every number of which is already on `Result`.

3. **Cross-craft handoff.** The masterwork gate is asserted by the caller
   (`item={"masterwork": True, "kind": "weapon"}`). When the smith and leatherworker
   tracks land their outputs as stock, their masterwork products should carry a
   `masterwork: true` field so the enchanting bench can read the fact instead of asking
   the player to vouch. The vessel entries (`requires` prose) are the catalogue of what
   to accept. Until then, the GM vouches, and an unvouched item is refused — assuming
   masterwork would wave every rusty sword through.

4. **Uniform dispatch.** Both modules now carry the same surface: `TRACK_ID`,
   `CraftError`, `Chain`, `chain_from_body(body)`, `preview(level, chain, stock=None,
   actor=None, item=None)`, `check_terms`/`check_bonus`, and a `Result.as_dict()`
   carrying name, tier, rank, stages, dc, risky, problems, effects, specs, consumes,
   output, bonus, terms, chance. A `rules/benches.py` mapping `(track, mode) → module`
   can treat herbalism, the circle and the book as three entries in a dict. Two things
   to know: `preview` does not take `track_id` first (the module *is* the track — pass
   `TRACK_ID` rather than a free string), and `enchanter.preview` accepts both `actor`
   and the older `carrier` for the same argument, so an existing caller does not break.

5. **Awarding mastery.** `worldclass.award` works unchanged: `tier` from `Result.tier`,
   `stages` from `Result.stages`, `milestone` from `track.deed_done(tier=result.tier,
   success=True)`. `Result.risky` is now populated honestly by both modes — the circle
   sets it when the working stakes a fragile focus, the book mode leaves it False
   because patient workshop crafting has no hazard — so the award's risky term can read
   it directly.

6. **Registry.** Materials are not a `registry.KINDS` entry because registering one
   means touching `rules/registry.py`, which this slice must not. When someone adds a
   `"materials"` Kind (folder `materials`, key `materials`, shipped loader
   `rules.enchanter:materials`), the homebrew editor pages come free and
   `rules/enchanter.py.materials()` can collapse onto `registry.load_raw` — its own
   overlay walk is the seventh copy of the pattern the registry was written to delete,
   kept only because the alternative was editing a shared file in a parallel build. A
   second Kind for `magic-items` would want a different folder key, since that
   catalogue is a priced rules table rather than a shelf.

7. **The acquisition hub needs a scene and a purse.** `ACQUISITION` and `obtainable()`
   declare what each excursion yields; what they cannot answer is *how much* turns up,
   what a gathering roll is against, or whether the character can afford a 20,000 gp
   diamond. Those are scene and economy questions — the biome comes from the scene, the
   creature from a corpse in it, and `price_gp` is a number waiting for a purse the
   sheet does not carry yet. The excursion should also be able to hand back a
   `from_creature` match by *creature id* rather than the substring match used here,
   once the bestiary's ids are what the play layer passes.

8. **What the potion contract needs from alchemy.** This mode reads exactly two fields
   off a stock entry — `holds_spell` and `caster_level` — and consumes one dose. It does
   not yet check that the potion's caster level meets the item's minimum, because the
   book's rule there ("the caster level of the item") is about the *creator*, not the
   potion, and inventing a stricter rule would have been a house rule nobody asked for.
   If the alchemist track wants that gate, it is one comparison and belongs in the same
   refusal sentence.
