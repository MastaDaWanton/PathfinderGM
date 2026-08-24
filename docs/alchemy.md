# Alchemy

The second world class, and the proof that `rules/worldclass.py` meant what it said:
Alchemist is one more JSON file and one more chain-rules module, not one more code path.

**Namespace note (read once, then forget):** "alchemist" here is the *world class* —
`rules.worldclass.get("alchemist")`, chain rules in `rules/alchemist.py` — and it is not
the PF1e Alchemist *character class* in `content/classes/` (`rules.classes.get`). A Rogue
is an Alchemist here the way a Fighter is an Herbalist: by doing the work. The two
namespaces share a word and nothing else.

## The craft's fiction

The Herbalist works with what the world grew. The Alchemist works with what the world is
*made of* — and the world's materials have opinions. Brimstone wants to burn. Saltpetre
does not burn at all, but everything near it burns harder. Quicksilver dissolves gold like
a rumour and poisons the alchemist a tremor at a time; nobody ever feels the dose that
mattered. Alkahest dissolves everything, which is the problem — "everything" includes the
flask, the bench, and the argument for having bought it.

So where herbalism's discipline is knowing *where things grow and when to pick them*,
alchemy's discipline is **containment**. The whole craft is a negotiation between what a
reaction can produce and what a vessel can survive, and the two methods at its centre say
so: **react** is the dangerous heart — setting two prepared substances against each other
and keeping what the violence makes — and **stabilize** is what keeps the violence in the
product instead of in your face. They are learned together at level 3, on purpose: a band
of levels where you could react but not stabilize would be a band where the two-volatile
rule could never be satisfied.

The tiers climb from the apothecary's shelf to the impossible. Common is anything a
market town sells: sulphur, nitre, lime, vinegar. Uncommon is where the trade starts
charging — quicksilver, strong acids, the first monster glands. Rare is where the
materials start being *arguments*: alkahest, basilisk humour, dragon bile. Exotic is the
planes leaking into jars — phlogiston, bottled weather, demon ichor. Legendary is the
great work itself: prima materia, philosopher's mercury, the unspent centre of a fallen
star.

## The track

Thresholds are the Herbalist's (25 / 65 / 50 / 100), because both tracks pay mastery from
the same `MP_AWARDS` table and a chain here must be worth what a chain there is worth.
The dip at level 4 is the Herbalist's measured dip; `herbalist.json` documents it.

Level 5 waits on a deed as well as points: **legendary-work**, any successful craft at
legendary tier however it was reached. The deed is the *material*, not the method —
`catalyze` is a level-5 method, and a deed requiring it would gate the level behind
itself, which is the exact trap the Herbalist's deed already walked into and out of.

## The method table

| Method | Level | Shape word | What it does |
|---|---|---|---|
| calcine | 1 | Calx | Roasts a material to its essential salt. Strips water and rot; the ash keeps indefinitely. |
| dissolve | 1 | Solution | Takes a material up into a solvent. Most chains start here — the bench works solutions, not lumps. |
| seal | 1 | Sealed Flask | **The finishing method.** Closes the work into its vessel; nothing follows a seal, and nothing reacts inside a sealed flask. An unsealed preparation is bench-work, not an item. |
| filter | 2 | Filtrate | **The cleansing method.** Holds back what does not belong: strips poisons and penalties, keeps the benefits. Refused when there is nothing harmful to remove. |
| precipitate | 2 | Precipitate | Drives a dissolved substance back out as a concentrated solid — how a solution becomes a powder worth keeping. |
| react | 3 | Admixture | **The dangerous heart.** Two prepared substances set against each other; +25% to the primary effect. Needs a solvent (or a liquid intermediate) as its medium. |
| stabilize | 3 | — | Buffers a reaction. Required before two volatile materials share a vessel, and the only answer to a material that attacks its own flask. Shapes nothing — it is how a reaction is survived, not what it makes. |
| sublime | 4 | Sublimate | Vapour to crystal in the athanor; +25%. The exotic tiers are worked almost entirely as sublimates. |
| catalyze | 5 | Arcanum | Legendary material driving a transformation it does not join; 150% of base strength. |

The shape words deliberately never collide with herbalism's (`crafting.SHAPE_WORDS` —
Powder, Tea, Tincture, Infusion, Elixir, Catalyst…), because herbalism reads shape words
off jar names to answer questions like "is this a tincture", and a shared word would make
an alchemist's product answer them.

**Tools.** Level 1 travels (alchemy kit, iron crucible). Level 2 is glassware (alembic,
filter frames). Levels 3–5 are furniture — laboratory, athanor, philosopher's bench —
declared in `fixed_tools`, so whether a chain can be attempted is partly a question about
where the character is standing, exactly as the Herbalist's still and workbench are.

## Volatility

Alchemy's signature rule, and the one herbalism has no counterpart for.

- A material marked `volatile` fights back on the bench. About a quarter of the
  catalogue is (pinned by test at ≥ a fifth).
- **Two volatiles in one vessel without `stabilize` is refused before any roll:**
  *"Two volatile materials in one vessel is an explosion, not a preparation. Stabilize
  the chain, or take one out."*
- **Each volatile past the first adds +3 to the DC** (`VOLATILE_DC_STEP` — +3 rather
  than +2 so the itemised DC's surcharge term is visibly not the per-stage bump). The
  preview itemises it: `common material 10 · 4-stage chain +6 · 3 volatile materials +6`.
- **The mishap stakes scale and are written into the preview**: one volatile, the jar
  spends itself on the bench and the alchemist takes its effect at half strength; two or
  more, everything is lost and the alchemist takes the strongest effect at full strength.
- A material flagged `needs_stabilizer` (alkahest, phlogiston, starfall core) attacks
  its own vessel and wants stabilizing *even alone*.

Quicksilver shows the other face of risk: it is not volatile at all — it will never blow
up a chain — but the handler pays a slow non-lethal poison tax per unmasked working, the
same way Blood Bending abilities pay their costs non-lethally. Volatile means the
*reaction* is dangerous; risky means the *material* is.

## The DC

`crafting.py`'s rule, restated with one new term: an authored `craft_dc` beats a derived
one; otherwise 5 + 5 × tier rank; +2 per stage past the first; +3 per volatile past the
first. Costs and penalties round down, benefits round up — potency is carried as a float
and applied at use time by `consumables.scale`, which already rounds the house way.

## The reagent catalogue

116 materials in `content/materials/alchemist-materials.json`, by kind and tier.
Mechanical identities in brackets; entries without one carry their identity as prose.

### Reagents (26)
- **Common:** brimstone *(volatile; 1d6 fire — the heart of alchemist's fire)*,
  saltpetre *(volatile; makes everything near it violent)*, willow charcoal *(+1 Fort vs
  ingested poison — antitoxin's body)*, green vitriol, blue vitriol *(risky; DC 12 Fort
  or sickened 1d4 rounds)*, pine pitch *(entangled 2d4 rounds — the tanglefoot body)*,
  birch tar, iron filings, lead dust *(risky; 1d2 non-lethal poison to the handler)*,
  powdered chalk, lamp black.
- **Uncommon:** quicksilver *(risky, DC 15; 1d3 non-lethal poison to the handler — the
  price is the alchemist's, not the target's)*, phosphorus *(volatile, risky; 1d4
  fire)*, antimony regulus, realgar *(risky; DC 14 Fort or 1d2 Con)*, cinnabar,
  verdigris, storm quartz *(volatile; DC 15 Fort or deafened 1 hour — the
  thunderstone)*, smoke resin *(10-ft cube of smoke)*, itchweed floss *(DC 12 Fort or −2
  attack — itching powder)*, bitter aloes *(+1 Fort vs ingested poison)*,
  dragon's-blood resin.
- **Rare:** white phosphorus *(volatile, risky; 2d4 fire, keeps burning)*,
  salamander ash *(resist fire 5, 1 hour)*, sunmetal filings *(1d6 positive vs undead)*,
  pyre gel *(volatile; 1d6 fire that clings)*.
- **Exotic:** ectoplasm residuum *(the work touches the incorporeal)*, star-iron dust
  *(+1 alchemical damage, 1 hour)*, void — see salts.
- **Legendary:** prima materia *(volatile; becomes anything the chain asks)*,
  starfall core *(volatile, needs stabilizer; 5d6 fire)*.

### Solvents (12)
- **Common:** distilled water, strong spirits *(volatile)*, white vinegar, lamp oil
  *(volatile; 1d3 fire when lit)*, turpentine *(volatile)*, lye water *(risky; 1d2
  acid)*, brine *(the cheap precipitant)*.
- **Uncommon:** oil of vitriol *(risky; 1d6 acid — the acid flask)*, aqua fortis
  *(risky; 1d4 acid)*, naphtha *(volatile; 1d6 fire — the accelerant half of
  alchemist's fire)*, rectified spirits *(volatile)*.
- **Rare:** alkahest *(volatile, risky, needs stabilizer, DC 25; 2d6 acid — dissolves
  the vessel too)*, aqua regia *(risky; 1d8 acid — dissolves gold)*.
- **Exotic:** azoth *(volatile, risky, DC 26; heals 2d8 — the solvent that is also the
  medicine)*.

### Salts (9)
quicklime *(common; volatile, risky; 1d3 fire on contact with water)*, natron, rock
salt, alum *(+1 Heal to staunch bleeding)*; sal ammoniac, sal volatile *(ends dazed —
smelling salts)*, silver salt *(+2 Fort vs disease — antiplague's anchor)*; ghost salt
*(rare; 1d6 negative)*, everfrost salt *(rare; 1d6 cold — liquid ice)*, void salt
*(exotic; 2d6 cold)*.

### Glands (20)
- **Common:** fire beetle gland *(light, 10 ft, 1d6 days — sunrod's heart)*, skunk musk
  gland *(DC 13 Fort or sickened)*.
- **Uncommon:** ankheg acid sac *(2d4 acid)*, shocker-lizard node *(volatile; 1d8
  electricity)*, giant frog mucus *(DC 15 Ref or entangled)*, adder venom gland *(DC 13
  Fort or 1d2 Con — and antitoxin's seed)*, slick jelly *(alchemical grease)*.
- **Rare:** basilisk eye *(DC 20 to work; DC 15 Fort or staggered while the flesh greys
  toward stone, a drop at a time)*, cockatrice wattle *(the lesser dose)*, dragon bile
  *(volatile; 3d6 fire)*, frostworm chill gland *(2d6 cold)*, winter wolf humour
  *(resist cold 5)*, gray ooze core *(2d4 acid, eats metal)*, wyvern venom gland *(DC 17
  Fort or 1d4 Con)*, troll marrow *(fast healing 1)*, drake's breath sac *(volatile; 2d4
  fire in a cone)*.
- **Exotic:** demon ichor *(volatile; 2d6 acid, scars black)*, purple worm venom *(DC
  24 Fort or 1d3 Str)*, remorhaz thermal gland *(volatile; 3d6 fire)*.
- **Legendary:** dragon heart-blood *(volatile; 4d6 fire)*, linnorm venom *(DC 26 Fort
  or 2d6 Con)*, tarrasque humour *(fast healing 5)*.

### Essences (9)
camphor *(common; volatile; +1 Fort vs disease — antiplague, vermin repellent)*;
wintergreen *(+2 Heal)*, oil of cloves *(numbs)*; essence of ether *(rare; volatile; DC
13 Fort or staggered)*; fire-elemental ember *(exotic; volatile; 3d6 fire and resist
fire 10)*, bottled thunderhead *(exotic; volatile; 3d6 electricity)*, shadow essence
*(exotic; DC 17 Fort or 1d6 Str — the assassins' classic)*, angel tears *(exotic; heals
3d8, ends sickened)*; phoenix ash *(legendary; volatile; heals 4d8, ends fatigue)*,
quintessence *(legendary; 20 temporary hp for an hour)*.

### Catalysts (8)
brewer's yeast, mother of vinegar, rennet *(common)*; lodestone powder *(uncommon)*;
philosopher's wool *(rare; heals 1d4)*, mithral dust *(rare)*; philosopher's mercury
*(legendary; risky — transformation that is never itself spent)*, orichalcum grains
*(legendary; steers the work toward what was meant)*.

### Vessels (12)
clay flask *(shatters — the splash-weapon vessel)*, glass vial, waxed bladder *(bursts —
the tanglefoot vessel)*, stoneware pot *(common)*; iron flask, lead-glass vial *(holds
acid)*, brass casing *(bursts evenly)* *(uncommon)*; crystal retort, salamander-glass
flask *(holds fire)*, warded phial *(holds the grave tiers)* *(rare)*; genie-breath
phial *(holds vapour forever)*, adamantine crucible *(the one vessel alkahest merely
sulks in)* *(exotic)*; world-egg shell *(legendary)*.

### Treatments (8)
rendered tallow, beeswax *(seals, preserves)*, cork-and-wick *(fuse-and-stopper)*,
oilcloth wrap, fuller's earth *(common)*; quick-match cord *(uncommon; volatile)*;
quenching clay *(the physical half of stabilize)*, saint's tallow *(1d4 positive vs
undead on a coated blade)* *(rare)*.

## The classic-output recipe table

Which CRB (and beyond-CRB) item wants which chain. The material is the identity; the
chain is the item. All are sealed, because an unsealed preparation is bench-work.

| Item | Materials | Chain |
|---|---|---|
| Alchemist's fire | brimstone + naphtha, clay flask | dissolve → react → seal |
| Acid flask | oil of vitriol (or ankheg acid sac + a solvent), lead-glass vial | dissolve → react → seal |
| Tanglefoot bag | pine pitch + giant frog mucus + turpentine, waxed bladder | dissolve → react → stabilize → seal |
| Thunderstone | storm quartz + saltpetre + distilled water, brass casing | dissolve → react → stabilize → seal |
| Smokestick | smoke resin + lamp black + saltpetre, distilled water | dissolve → precipitate → seal |
| Tindertwig | phosphorus + brimstone, turpentine | dissolve → precipitate → stabilize → seal |
| Sunrod | fire-beetle gland + phosphorus, distilled water | dissolve → react → stabilize → seal |
| Antitoxin | adder venom gland + willow charcoal + bitter aloes, white vinegar | dissolve → filter → seal |
| Antiplague | silver salt + camphor, distilled water | dissolve → filter → seal |
| Alchemical grease | slick jelly + rendered tallow, turpentine | dissolve → react → seal |
| Itching powder | itchweed floss | calcine → precipitate → seal |
| Alkali flask | quicklime + brine | dissolve → precipitate → stabilize → seal |
| Liquid ice | everfrost salt + distilled water | dissolve → react → seal |
| Flash powder | phosphorus + saltpetre + strong spirits | dissolve → react → stabilize → seal |
| Smelling salts | sal volatile + sal ammoniac | calcine → precipitate → seal |
| Vermin repellent | camphor + skunk musk gland, tallow | dissolve → filter → seal |
| Bladeguard | verdigris + beeswax, turpentine | dissolve → precipitate → seal |
| Holy weapon balm | saint's tallow + sunmetal filings, rectified spirits | dissolve → react → stabilize → seal |

Eighteen named outputs against the CRB's eleven classics — the shelf out-writes the book,
which was the target.

## Potions that hold spells

The trade's real product is not acid. It is a spell in a bottle, and that is what makes
alchemy matter to a party with no caster in it.

`content/materials/alchemist-spell-potions.json` holds **44 hand-converted potions** of
1st-3rd level spells. It is a *curated* conversion, not a bulk one, because
`content/spells/spells.json` carries 3,040 spells as **prose only** — no structured
effects — so every entry here was read and encoded by hand.

**Every `spell` id is verified against that corpus by test.** This is not ceremony: the
check caught three wrong names on the first run. The brief asked for `lesser-restoration`,
`mage-armour` and `eagle-s-splendour`; the corpus spells them `restoration-lesser`,
`mage-armor` and `eagle-s-splendor`. A potion of a spell the app has never heard of is
exactly the "ground every name" failure CLAUDE.md records.

**`holds_spell` is a cross-craft contract.** A brewed potion's `Result.output` carries
`holds_spell: "<spell-id>"`, `caster_level`, `usable: True` and `how`. The enchanter reads
`holds_spell` to decide that a potion of X stands in for knowing X. The field name is
fixed — nothing else on the item identifies the spell.

**Caster level is 1e's minimum** for the spell level (CL 1 / 3 / 5 for 1st / 2nd / 3rd),
and every duration and die in the file is *that caster level already worked out*. A card
reading "minutes/level" makes the player do arithmetic the bench already knows.

**Materials are the spell's own printed component** wherever 1e prints one — enlarge
person is brewed with the powdered iron the spell itself calls for, spider climb with
bitumen and a live spider, comprehend languages with soot and salt. The medium sets the
tier and therefore the level gate:

| Spell level | Caster level | Medium | Tier | Needs |
|---|---|---|---|---|
| 1st (15 potions) | CL 1 | rectified spirits / font water | uncommon | Alchemist 3 |
| 2nd (20 potions) | CL 3 | + a rare catalyst (philosopher's wool, mithral dust) | rare | Alchemist 3 |
| 3rd (9 potions) | CL 5 | azoth, in a crystal retort | exotic | Alchemist 4 |

React is in every potion chain, which is why potion-brewing is a laboratory art rather
than roadside work. A recipe **cannot lie about its tier** — a test derives the tier from
the materials and asserts the declaration matches, because the tier is what gates who may
brew it.

**Matching is strict**: the exact set of materials *and* the exact method sequence. A
near-match produces an ordinary preparation, never a different potion. "You got blur
because you were one reagent short of invisibility" is a bug report nobody could write.

### The user's example, end to end

Potion of Enlarge Person: `rectified-spirits + iron-filings + glass-vial`, chain
`dissolve → react → seal`. It produces **live specs, not prose** — +2 Strength and −2
Dexterity as *size* modifiers, −1 attack and −1 AC, with the reach and space change as the
one narrative line the vocabulary genuinely cannot hold. The engine applies the numbers
through `consumables.plan`'s `buff` op; only the reach sentence is narrated.

Where a spell's mechanic has no home in the vocabulary it stays `narrative` and is never
guessed at. Two cases recur: **drinker-chosen targets** (lesser restoration mends "one
ability score of your choice" — picking one here would invent a fact the spell never gave)
and **effects with no vocabulary counterpart at all** (gaseous form, water breathing,
blur's miss chance). All 44 potions' specs validate; zero are invented.

## Acquisition — where materials come from

The craft-action button is becoming the single hub for *obtaining* materials, replacing
the foraging panel inside the crafting menu. Alchemy has no forage panel of its own
because gathering is one of four ways in, not the way in.

Every one of the 137 materials declares `obtain`, authored per material rather than
derived from `kind` — a heuristic on kind would have said "buy a basilisk eye at the
apothecary".

| Excursion | `obtain` | Needs | Count | Examples |
|---|---|---|---|---|
| `market-run` | bought | a market | 71 | quicksilver 25 gp (apothecary), azoth 1,500 gp (planar broker) |
| `quarry` | mined | a biome | 13 | brimstone (mountain/underground, DC 12), star-iron dust (desert/tundra, DC 20) |
| `field-gathering` | gathered | a biome | 17 | pine pitch (forest, DC 8), ghost salt (underground, DC 18) |
| `harvest-reagents` | harvested | a creature | 36 | ankheg acid sac (DC 15), tarrasque humour (DC 35) |

Markets are named, not generic: `market`, `apothecary`, `glassblower`, `smith`, `temple`,
`planar broker`. An apothecary sells brimstone; a planar broker sells azoth and asks no
questions.

The **shape is the one the other three crafts use** — flat `obtain` string with `biomes`,
`from_creatures`, `market`, `price_gp` and `obtain_dc` beside it. This track started with
a nested dict and conformed: the shelf is shared and one hub reads all four catalogues, so
the odd craft out changes rather than making the hub learn two shapes. `Material.from_dict`
still reads both, and reads the enchanter's singular `from_creature` as well as the
leatherworker's plural `from_creatures`.

`ACQUISITION` (in `rules/alchemist.py`) declares the four excursions as data — id, label,
which `obtain` kind it serves, what it needs, and a blurb — so the page asks *what the
track offers* rather than knowing what alchemy is. `obtainable(kind, biome=, creature=)`
answers with the matching materials, shelf-wide, sorted by tier.

## Icons

`KIND_GLYPH` maps each kind to one glyph from this track's reserved pool. Herbalism owns
🌿 herb, 🍄 fungus, 🦴 monster part and ☠️ poison; none of them appear here, because a
repeated glyph on a shared shelf makes two different things look like the same thing.

| 🜂 reagent | 🧪 solvent | 🧂 salt | 💠 catalyst | 🔆 essence |
|---|---|---|---|---|
| **🩸 gland** | **🫙 vessel** | **🧫 treatment** | **🧊 intermediate** | **⚱️ potion** |

## Method help

`alchemist.json` carries `method_help` beside `method_descriptions` — one entry per
method, with three fields, because a player mid-chain is only ever asking one of three
questions:

- **does** — the mechanical effect in numbers (×1.25 potency, +3 DC per extra volatile,
  what gets removed)
- **needs** — what must be in the vessel for the method to be legal
- **for** — what a player reaches for it to accomplish

`method_descriptions` stays: it is the rulebook voice, where `method_help` is the bench
voice. A test asserts every method has both.

## The dispatchable surface

`rules/alchemist.py` mirrors `rules/crafting.py` so the shared bench can route a chain by
track without learning two vocabularies:

- `TRACK_ID`, `CraftError`, `Chain`, `Result`, `materials()`, `preview()`
- `chain_from_body(body)` — parses `methods`, `materials`, `name`, `stock`, tolerant of
  every key being absent. A missing key becomes an empty list, never a 500; the refusal
  belongs in `problems` where the page can show it.
- `check_terms(actor, level)` / `check_bonus(actor, level)` — **d20 + track level + half
  character level + Intelligence**. Int rather than herbalism's Wis because Craft is
  Int-based in PF1e, and that single substitution is what makes an alchemist a different
  character from a herbalist rather than the same one with two shelves.
- `preview(level, chain, stock=None, actor=None)` — with an actor it sets `bonus`, `terms`
  and `chance`; without one it answers "is this legal" rather than "will I make it", and
  `chance` stays 0 so no page can show a tempting percentage on a refused chain.

`Result.output` is the inventory item: `id, name, kind="crafted", craft, tier, rank,
count, effects, specs, from_materials, usable, how, wearable=False, slot=None,
holds_spell, caster_level`. **How an item is used is read off what is in it**, not
declared per recipe, because the rule has to answer for chains nobody wrote down: *a
vessel is what makes a thing throwable* — harmful in a vessel is a splash weapon
(alchemist's fire, acid flask), harmful without one is a coating (grease, holy balm), and
anything not harmful is drunk.

## Worked examples

### Alchemist's fire (level 3, the trade's handshake)

Materials: **brimstone** (common, volatile, 1d6 fire), **naphtha** (uncommon, volatile,
1d6 fire — and the solvent). Chain: `dissolve → react → stabilize → seal`.

- Two volatiles, so the chain *must* stabilize — without it: *"Two volatile materials in
  one vessel is an explosion, not a preparation."*
- Tier: uncommon (naphtha's), so this wants Alchemist 2 for the material and 3 for
  react/stabilize.
- DC, itemised: uncommon base 15 (5 + 5×2) + 6 (three stages past the first) + 3
  (second volatile) = **24**.
- Potency: react ×1.25. Output: *"Brimstone Sealed Flask"* (or name it), 1d6 fire
  scaled at use by `consumables.scale` — 1d6+1 — thrown as a splash weapon from its
  clay flask.
- Mishap, stated in the preview: everything is lost and the alchemist takes the
  strongest effect at full strength.

### Antitoxin (level 2, the gentle chain)

Materials: **adder venom gland** (uncommon, risky — DC 13 Fort or 1d2 Con), **willow
charcoal**, **bitter aloes**, in **white vinegar**. Chain: `dissolve → filter → seal`.

The poison goes *in* — the cure is taught by the poison — and **filter** takes the harm
back out: the gland's save-gated Con damage is stripped from the specs themselves (not
just the card; that is the purify lesson crafting.py paid for), leaving the charcoal's
and aloes' +1 Fort vs ingested poison. No volatiles, no surcharge. DC: uncommon base 15
(the gland sets the tier) + 4 for two stages past the first = **19**, itemised at the
bench. The result is a draught, drunk.

### Tanglefoot bag (level 3)

**Pine pitch** (entangled 2d4 rounds) + **giant frog mucus** (DC 15 Ref or entangled) in
**turpentine** (volatile), sealed in a **waxed bladder**: `dissolve → react → stabilize →
seal`. One volatile only — the stabilize is for the setting reaction, and mechanically it
future-proofs the chain when a second volatile joins it. Thrown, it bursts rather than
shatters; the Reflex gate and the entangle ride the specs into `consumables.plan`.

### The Unmaking of the Star (level 5, legendary)

**Starfall core** (legendary, volatile, needs stabilizer, DC 30, 5d6 fire) + **prima
materia** (legendary, volatile) in **azoth** (exotic, volatile), worked in the
**world-egg shell**: `dissolve → react → stabilize → sublime → catalyze → seal`.

Three volatiles (+6), a stated DC 30 base, six stages (+10): **DC 46**, itemised, with
the mishap line reading like an obituary. Potency 1.25 × 1.25 × 1.5 ≈ ×2.34. Succeed and
the deed `legendary-work` unlocks Alchemist 5 for whoever was still 4; the output is a
sealed arcanum that hits like the falling star it politely used to be.

## Integration notes — wanted from the shared spine, deliberately not touched

None of `play/*`, `rules/sheet.py`, `rules/crafting.py`, `rules/consumables.py`,
`rules/casting.py` or any sibling track's files were modified.

1. **Bench UI** (`play/` templates and views). `alchemist.Result.as_dict()` carries every
   key the brief specified plus `dc_terms`, `volatiles` and `mishap`, which want three
   small additions: the itemised DC beside the button (the way `terms` itemises the
   bonus), a volatility marker on each jar, and the mishap sentence under the chance
   label. Nothing in the Result requires new page machinery.

2. **The acquisition hub** (craft-action excursion). `ACQUISITION` declares four
   excursions and `obtainable(kind, biome=, creature=)` answers them; the data is in
   place for all 137 materials. What the hub still needs from the spine is the *scene*
   half — which market the party is standing in, which biome they are in, and which
   corpse is in front of them. `obtainable` takes those as arguments and has no opinion
   about where they come from.

3. **Consumables wiring** (`rules/consumables.py`). A sealed flask should be throwable
   exactly like a tincture. `Result.output` already carries `specs` (`from`-marked per
   material, which is what `consumables.poisons` groups on), `potency` and `how`, so
   building a `Stock`-alike from it and calling `consumables.plan` should just work.

   **One real gap found**: `consumables.plan` refuses `coat` unless `is_harmful(stock)`,
   and a *beneficial* weapon oil is not harmful. Oil of magic weapon, oil of align weapon
   and oil of keen edge are `how: ["coat"]` and would all be refused today with "does
   nothing harmful, so there is nothing to put on a blade". The spine needs a benign-
   coating path — a coating whose specs buff the *wielder's weapon* rather than poisoning
   the target. Four of the 44 potions are affected. I have not touched `consumables.py`,
   so the declaration stands and the refusal is real until that path exists.

4. **Engine dispatch** (`rules/engine.py` craft op). `TRACK_ID`, `CraftError`, `Chain`,
   `chain_from_body`, `check_terms`, `check_bonus` and `preview` all mirror crafting.py's
   names, so the dispatcher can be a table keyed on track rather than an if-ladder.

5. **Spell potions and the caster spine** (`rules/casting.py`, the enchanter).
   `holds_spell` is the contract and is populated. What it needs from the spine is a
   consumer: something that reads `holds_spell` off an inventory item and treats it as
   access to that spell. I have deliberately not guessed at that API.

6. **Mastery scoring**. `worldclass.award` needs nothing new — stages, risky and tier all
   fall out of `Result`, and the volatile surcharge is already reflected in the DC rather
   than needing its own award row.

7. **A shared-shelf hazard, now pinned by test.** `content/materials` is one directory and
   `load_dir` merges by id in filename order, so a duplicate id means the alphabetically
   later craft silently wins. My `blessed-water` (uncommon solvent) was being shadowed by
   the blacksmith's `blessed-water` (rare quenchant): it moved four potions up a tier and
   removed the reaction medium from three chains, with nothing anywhere reporting a
   problem. Mine are renamed `font-water` and `standing-oak-bark`, and
   `test_no_material_id_is_claimed_by_two_crafts` now checks the whole shelf, not just
   this track — the next collision will not be mine either.
