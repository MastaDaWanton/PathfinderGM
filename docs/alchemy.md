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

## Integration notes — wanted from shared code, deliberately not touched

Written for whoever wires the bench next; none of these files were modified.

1. **Bench UI** (`play/` templates and views). Herbalism's bench renders
   `crafting.Result`; `alchemist.Result` is the same shape plus `dc_terms`, `volatiles`
   and `mishap`, which want three small additions: the itemised DC beside the button
   (the way `terms` itemises the bonus), a volatility marker on each jar, and the mishap
   sentence under the chance label. Nothing in the Result requires new page machinery.

2. **The craft-action excursion** (`rules/craft_action.py`, foraging). Herbs are
   foraged; materials are *bought, mined or harvested from kills*. The catalogue
   deliberately has no `biomes`/`forageable` fields. Gathering wants the excursion
   verb pointed at markets and carcasses — an ankheg acid sac should come from an
   ankheg the table actually killed, through the same "GM hands it over" path
   `ingredients.by_name` serves.

3. **Consumables wiring** (`rules/consumables.py`). A sealed flask should be throwable
   exactly like a tincture: build a `crafting.Stock` (or its dispatcher-generalised
   successor) from `alchemist.Result.specs` with `craft="alchemist"`, and
   `consumables.plan` already handles drink/throw/coat, splash radius, per-source
   poison gates and potency scaling. The specs are already `from`-marked per material
   for exactly that grouping.

4. **Engine dispatch** (`rules/engine.py` craft op). The `craft` intent currently
   assumes herbalism's preview. `TRACK_ID`, `CraftError`, `Chain`, `preview` here
   mirror crafting.py's names so the dispatcher can be a two-entry table rather than
   an if-ladder.

5. **Mastery scoring**. `worldclass.award` needs nothing new — stages, risky and tier
   all fall out of `Result` (`stages`, `risky`, `tier`), and the volatile surcharge is
   already reflected in the DC rather than needing its own award row.
