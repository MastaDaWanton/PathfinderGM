# Leatherworking

The Leatherworker world class: what it is in fiction, how the chain rules read, the
full material catalogue, and worked examples. The data lives in
`content/world-classes/leatherworker.json` and
`content/materials/leatherworker-materials.json`; the chain semantics in
`rules/leatherworker.py`; the pins in `tests/test_leatherworker.py`.

## The craft

Herbalism turns what grows into what heals. Leatherworking turns what a fight leaves on
the ground into what the next fight is survived in. The two crafts share a skeleton —
tiers, methods, chains, a clock on fresh material — and differ in every physical fact:
herbs steep, hides spoil; a tea is drunk once, a breastplate is worn for a career.

Three facts drive every rule, and each is a rule the player learns once:

1. **A green hide is meat.** The spoilage clock starts at the skinning — 48 hours, the
   same clock as any animal part — and stops only when the hide is cured or tanned.
   Stitching a green hide sews a bag of rot, so the bench refuses it.
2. **Tanning is chemistry, not soaking.** It needs a tannin, and the tannin must be
   equal to the hide: within one tier. Oak bark binds a deer. Dragonhide accepts
   nothing short of liquor quickened with dragon's blood, which is why the tannin
   ladder climbs all five tiers.
3. **Cuir bouilli is done to leather.** Boiling tanned leather in wax sets it like thin
   steel; boiling raw hide makes glue. Hardening what was never tanned is refused, not
   weakened.

The tier ladder is the bestiary's own: the tier of a hide follows the beast it came
off. A deer is common work, a dire bear uncommon, a shadow mastiff rare, a wyvern
exotic, a dragon legendary. Dragonhide is the book's special material — masterwork by
nature, metal-free so a druid may wear it, and carrying the energy ward of its colour.

## The track

Five levels, five stations. Thresholds are the herbalist's curve (25 / 65 / 50 / 100,
dip at 4 deliberate — see the `_thresholds_note` in the track file). The level-5
milestone is the deed of working legendary hide, by any successful means; masterwork
tooling is the mastery that follows the deed, not the gate in front of it.

| Level | Max tier | Tools | Methods learned |
|---|---|---|---|
| 1 | common | skinning knife, fleshing beam | skin, flense, cure, cut, stitch |
| 2 | uncommon | tanning rack, bark vats | tan, oil |
| 3 | rare | dye vats, half-moon knife, stitching pony | dye, line |
| 4 | exotic | wax kettle, hardening trough | harden |
| 5 | legendary | master tannery | tool |

### Methods

| Method | What it does |
|---|---|
| **skin** | Takes the hide off a fallen creature *in the field*. Never a bench step — every hide on the bench already went through it, and the clock started when it did. |
| **flense** | Scrapes fat and flesh over the beam. Comes before cure or tan: flesh under the salt putrefies. |
| **cure** | Salts a green hide; the spoilage clock stops. Cured rawhide keeps forever but is not yet leather. |
| **cut** | Panels, straps and pieces to pattern. Straps are cut work and nothing more. |
| **stitch** | Sews cut pieces into a finished thing. Needs thread; only cured or tanned hide takes a seam. |
| **tan** | Steeps a flensed hide in tannin liquor until it is leather through and through. Needs a tannin within one tier of the hide. A tanned hide never spoils. |
| **oil** | Dresses leather so it stays supple and serves longer (potency ×1.10). Needs an oil; some oils carry their own character into the piece. |
| **dye** | Colours the piece. Needs a dye; the rare ones do more than colour. |
| **line** | Builds a piece as two hides — working outer, soft or furred inner — so both hides' qualities ride in one garment. Needs two hides on the bench. |
| **harden** | Cuir bouilli (potency ×1.25). Needs a wax and *tanned* leather. The heart of leather armour. |
| **tool** | Masterwork finishing (potency ×1.25). Finishes the chain — nothing follows it. The only standard dragonhide accepts. |

### Products

A chain aims at a product pattern; the pattern names its assembly method and how big a
hide it wants. The piece has to come out of the hide — a cat does not contain a
warhorse.

| Product | Assembled by | Minimum hide |
|---|---|---|
| armour piece | stitch | medium |
| satchel, sheath, boots, bracers | stitch | small |
| straps | cut | small |
| cloak | stitch | medium |
| barding | stitch | large |

### The numbers

- **DC** = the hardest material's authored `craft_dc`, or `5 + 5 × tier rank`, plus
  `+2` per stage beyond the first — the same two terms as `crafting._dc`, deliberately.
- **Tier of the result** = the rarest component's tier, which is also what gates who
  can make it.
- **Rounding**: costs and penalties round down, benefits round up — the wearer is never
  surprised in the direction that hurts them. Resistance ratings are never scaled: the
  book says dragonhide resists 5, and potency does not un-book the book.

## The hide catalogue

Every hide names the bestiary creatures it comes off (`from_creatures`, matched as name
fragments against bestiary names) and carries a mechanical identity — as effect specs
where the vocabulary reaches (AC, resistances, skill bonuses, DR, saves), as `narrative`
specs where it does not (maximum-Dex preservation and armour check penalty are not in
the effect vocabulary, so they stay honest prose rather than guessed specs).

### Common hides

| Hide | From | Size | Mechanical identity |
|---|---|---|---|
| Deer Hide | deer, stag | M | Armour or clothing of deer hide never reduces the wearer's maximum Dexterity bonus |
| Boar Hide | boar | M | +1 Armour class against slashing weapons, worked into armour; Stiff: the armour check penalty of a piece made from it is one worse |
| Wolf Pelt | wolf | M | +1 Survival to endure cold weather |
| Dog Hide | dog | S | Takes every method without complaint; apprentice work of it sells as journeyman work |
| Cat Pelt | cat | S | +1 Stealth lining boots or gloves — the leather is silent |
| Horse Hide | horse | L | Large single panels: barding and tents need no joining seams, which is where cheap barding fails |
| Goat Hide | goat | S | Takes dye truer than any other common hide; dyed goods of it fetch half again the price |
| Viper Skin | viper, snake | S | +1 Escape Artist worked into sleeves or bindings |
| Crocodile Hide | crocodile | L | +1 Armour class back-plate panels, worked into armour; The plate panels are stiff as green wood: check penalty one worse unless only belly leather is used |
| Monitor Lizard Hide | lizard, monitor | M | Keeps its suppleness: armour of it never reduces maximum Dexterity bonus; +1 Acrobatics the leather flexes with the wearer |
| Toad Hide | toad, frog | S | Sheds water: contents of a toad-hide container stay dry through immersion |
| Bat-Wing Leather | bat | S | Takes the finest tooling; useless for armour — it tears like paper under a blade |
| Weasel Pelt | weasel | S | Trim and edging: raises the finished value of the garment it borders |
| Elk Hide | elk, dire stag | L | +1 Fortitude on checks against cold weather exposure |

### Uncommon hides

| Hide | From | Size | Mechanical identity |
|---|---|---|---|
| Dire Boar Hide | dire boar, boar | L | +1 Armour class worked into armour; DR 1/slashing; Heavy and stubborn: check penalty one worse |
| Winter Wolf Pelt | winter wolf, worg | L | Resist cold 2; The fur stays frost-rimed in any weather; snow does not melt on it |
| Boreal Wolf Pelt | boreal wolf, wolf | M | +2 Survival to endure cold weather |
| Black Bear Hide | black bear, bear | M | Sleeping gear of it counts as a warm camp in cold weather |
| Grizzly Hide | grizzly, bear | L | +2 Intimidate worn as a mantle, head and claws attached |
| Polar Bear Hide | bear, polar | L | Resist cold 2; +1 Stealth in snow and ice |
| Frostfallen Bison Hide | bison | H | Resist cold 1; Huge single panels: the largest seamless barding a tannery can produce below rare work |
| Glowlizard Hide | glowlizard | S | Sheds dim light in a 5-foot radius for a year; enough to read by, not enough to reveal the carrier at distance |
| Giant Frilled Lizard Hide | lizard, giant frilled | L | +1 Intimidate the frill worked into a flaring collar |
| Electric Eel Skin | eel, electric | M | Resist electricity 2 |
| Ankheg Shell Leather | ankheg | L | +2 Armour class plates worked over a leather backing; Resist acid 1; Plated and rigid: check penalty one worse |
| Snow Leopard Pelt | snow leopard, leopard | M | +2 Stealth in snow or broken shadow |
| Dire Wolverine Hide | wolverine | M | +1 Will against fear |
| Owlbear Hide | owlbear | L | Sheds rain completely; the wearer and their pack stay dry in any downpour short of immersion |
| Griffon Hide | griffon | L | +1 Handle Animal with birds of prey and flying mounts |

### Rare hides

| Hide | From | Size | Mechanical identity |
|---|---|---|---|
| Shadow Mastiff Hide | shadow mastiff | M | +2 Stealth in dim light or darkness; The leather is always slightly darker than its surroundings |
| Salamander Hide | salamander | M | Resist fire 5 |
| Hell Hound Hide | hell hound | M | Resist fire 2; +1 Intimidate it smells faintly of brimstone |
| Cave Bear Hide | cave bear | H | +1 Armour class worked into armour; DR 1/—; Massive: check penalty one worse, and no piece of it is light |
| Sabre-Tooth Tiger Hide | sabre-tooth, tiger | L | +2 Intimidate fangs mounted at the collar |
| Basilisk Hide | basilisk | M | +2 Armour class stone-grained scale, worked into armour; Polishes like marble; heavy — no piece of it counts as light armour |
| Bulette Plate | bulette | H | +3 Armour class overlapping plates, worked into armour or barding; Rigid plate: check penalty two worse |
| Manticore Hide | manticore | L | The spike-scarred grain takes tooled relief work of unusual depth; masterwork tooling of it is famous |
| Chimera Hide | chimera | L | Resist fire 1; No two panels match: the dragon-third resists flame, the goat-third takes dye, the lion-third takes tooling |
| Remorhaz Hide | remorhaz | H | Resist fire 5; Resist cold 2 |
| Gorgon Hide | gorgon | L | +2 Armour class iron scale, worked into armour; Rings when struck; takes metal polish, refuses oil and dye |
| Shadow Girallon Pelt | girallon | L | +2 Stealth in darkness; +1 Climb palm-panels grip like the beast did |
| Nightmare Hide | nightmare | L | Resist fire 2; Never takes dye: it comes out of any vat black. Faintly warm and smells of smoke |

### Exotic hides

| Hide | From | Size | Mechanical identity |
|---|---|---|---|
| Wyvern Hide | wyvern | H | +2 Armour class body scale, worked into armour; +1 Fortitude against poison — the venom's memory is in the grain |
| Behir Hide | behir | H | Resist electricity 5 |
| Purple Worm Plate | purple worm | G | +3 Armour class ring-segment plate, worked into armour; DR 2/—; Enormously heavy: check penalty two worse |
| Dragon Turtle Shell Leather | dragon turtle | H | Resist fire 5; +2 Armour class shell-margin plate, worked into armour |
| Couatl Feather Hide | couatl | L | +2 Will against enchantment; Iridescent: shifts colour with the light and cannot be dyed, disguised or mistaken |
| Hydra Hide | hydra | H | Self-mending: damage to the finished piece closes itself over a week; +1 Swim sheds water like the marsh it came from |
| Noble Salamander Hide | noble salamander | L | Resist fire 10 |
| Phoenix Feather Hide | phoenix | L | Resist fire 5; The feathers ember but never burn; the cloak sheds gentle warmth, and firelight through it casts no shadow |
| Unicorn Hide | unicorn | L | +2 Heal wound-dressings and sickbed furs of it; The forest that lost the beast knows the wearer on sight |
| Dragonne Hide | dragonne | L | +2 Intimidate the mane bristles when the wearer speaks; Resist fire 2 |

### Legendary hides

Dragonhide shares statistics by the book — masterwork, druid-legal, resistance 5 of the
dragon's element — so the colour identity is carried as its own spec, and the reskin
test in the suite keeps it there. Craft DC 30 authored on every dragonhide (35 for
tarrasque plate, 32 for kraken).

| Hide | Element | Notes |
|---|---|---|
| Red / Gold / Brass Dragonhide | fire 5 | Chromatic tyrant / freely given metallic / desert talker |
| White / Silver Dragonhide | cold 5 | Frosts in warm rooms / cloud-bright |
| Blue / Bronze Dragonhide | electricity 5 | Sand still singing in it / hums before storms |
| Black / Copper / Green Dragonhide | acid 5 | Glossy as tar / refuses a straight seam / smells of chlorine |
| Umbral Dragonhide | negative 5 | +2 Stealth in dim light; the shadow plane's own |
| Tarrasque Plate | — | +3 AC, DR 3/—; never shows wear |
| Kraken Hide | cold 2 | +2 Swim; immune to water damage and rot |

## Tannins

The tannin must be within one tier of the hide it binds — the ladder below is the
reason a sack of oak bark does not tan the whole bestiary.

| Name | Tier | What it does |
|---|---|---|
| Oak Bark | common | The standard tanning agent for common and uncommon hides |
| Sumac Leaf | common | Tans white: the leather takes dye with no brown undertone |
| Hemlock Bark | common | Fast: halves tanning time; the leather always comes out russet |
| Willow Bark | common | Tans supple: glove and lining leather of unusual softness |
| Tara Pod | uncommon | Strong and colourless: fine work that must stay pale |
| Bog Liquor | uncommon | Tans deep black-brown through; bog-tanned leather never rots |
| Mangrove Bark | uncommon | Salt-proof: endures seawater without hardening or cracking |
| Ironbark Tannin | rare | Bites monster-grade hide that common bark cannot bind |
| Wyrm Gall | rare | Opens and binds scaled hide; the stink takes a month to fade |
| Salamander Ash Lye | exotic | Binds fire-natured and planar hide; the vat must be stone |
| Styx Mordant | exotic | Fixes shadow-natured hide; a bare-skin splash costs the working day's memory |
| Dragonblood Tannin | legendary | The only tannin that binds legendary hide |

## Threads

| Name | Tier | What it does |
|---|---|---|
| Linen Thread | common | Waxed flax cord, the tannery's default |
| Sinew Thread | common | Shrinks tight: seams sewn with it are weatherproof |
| Gut Cord | common | Elastic: the seam stretches under load instead of tearing the leather |
| Horsehair Cord | common | Decorative seams and edging |
| Waxed Heavy Flax | common | Saddlery thread — it outlives the saddle |
| Silk Thread | uncommon | Invisible seams on fine work; raises the finished value |
| Spider Silk Cord | uncommon | Twice the strength of linen at a fifth the weight |
| Wire-Silk | rare | Seams that cannot be cut by an ordinary blade (the wire is the smith's work) |
| Shadow-Silk | rare | +1 Stealth in dim light, carried by every seam of the piece |
| Wyvern Sinew | exotic | Articulation thread: hardened plate sewn with it flexes at the joints |
| Dragon Sinew | legendary | Unbreakable: the seam outlasts the piece it closes |

## Oils and waxes

| Name | Kind | Tier | What it does |
|---|---|---|---|
| Neatsfoot Oil | oil | common | The everyday dressing |
| Tallow | oil | common | Waterproofs working leather |
| Fish Oil | oil | common | Softens leather to cloth-suppleness |
| Mink Oil | oil | uncommon | Conditions without darkening |
| Troll Fat | oil | rare | Self-mending finish: scuffs close overnight |
| Salamander Oil | oil | rare | Resist fire 1 |
| Wyvern Fat | oil | exotic | Hardened leather dressed with it never grows brittle |
| Umbral Oil | oil | legendary | +1 Stealth; the finish reflects no light |
| Beeswax | wax | common | Thread-wax and edge-seal |
| Pine Pitch | wax | common | Seals seams fully waterproof |
| Hardening Wax | wax | uncommon | The cuir bouilli medium: sets rigid without brittleness |
| Fireproof Wax | wax | rare | Resist fire 1 |
| Ghost Wax | wax | exotic | The sealed piece weighs half; sealed contents do not smell, even to scent |

## Dyes

| Name | Tier | What it does |
|---|---|---|
| Madder Red / Weld Yellow / Woad Blue / Walnut Brown / Iron Gall Black | common | Colour, honestly priced |
| Murex Purple | uncommon | The colour of rank: triples the finished value |
| Vermilion | uncommon | Ceremonial scarlet |
| Glowcap Green | uncommon | Glimmers faintly in total darkness |
| Shadow Black | rare | +1 Stealth in darkness — the outline will not resolve |
| Dragon's-Blood Crimson | rare | Reads as live embers in low light |
| Moonlight Silver | exotic | Moonlit in any light; sheds map-reading light in true darkness |
| Void Dye | legendary | +2 Stealth; viewers cannot afterwards describe the piece |

## Fittings and treatments

Fittings are the forge's goods, not the tannery's — `source: "smithed"` marks every
one, and the blacksmith track is where they will eventually be made rather than bought.

| Name | Kind | Tier | What it does |
|---|---|---|---|
| Iron Buckle / Brass Buckle / Bronze Rings | fitting | common | Workaday hardware |
| Steel Studs | fitting | common | +1 AC studding light armour — the studded-leather upgrade |
| Silver Clasps | fitting | uncommon | Counts as silver for what its touch harms |
| Cold Iron Studs | fitting | uncommon | Counts as cold iron for what its touch harms |
| Mithral Fittings | fitting | rare | The piece counts one step lighter to carry |
| Adamantine Buckles | fitting | exotic | Cannot be cut or sundered |
| Curing Salt | treatment | common | Stops the spoilage clock |
| Alum | treatment | common | Taws white and soft; reverts if soaked — not a true tan |
| Brain Tan Paste | treatment | common | The field tan: no vat, double work, must be smoked |
| Quicklime | treatment | uncommon | Strips hair before tanning; caustic |
| Mordant Salts | treatment | uncommon | Fixes rare and exotic dyes permanently |
| Planar Quench | treatment | exotic | Hardened leather keeps a planar trace |

## Worked examples

### A deer-hide satchel (Leatherworker 1)

The day's first lesson. A deer hide, skinned this morning, and a spool of linen.

- **Chain**: flense → cure → cut → stitch, over `deer-hide` + `linen-thread`,
  product `satchel`.
- **Refusals avoided**: skipping `cure` gets *"You cannot stitch an uncured hide — it
  rots"*; skipping the thread gets *"Stitching needs thread"*; putting `skin` in the
  chain gets *"the hide is already off the beast."*
- **Numbers**: common tier, 4 stages, DC 10 + 6 = **16**. Output: *Deer Satchel*,
  carrying the deer hide's identity (never fights the wearer's Dexterity).
- **Mastery**: 3 (first-time) + 6 (three extra stages) = 9 MP.

### A winter-wolf cloak, start to finish (Leatherworker 2)

The party brings down a winter wolf in the pass. The clock starts now.

1. **In the field**: `skin` the wolf — a craft-action excursion over the carcass, not a
   bench step. The pelt lands in stock with `age_hours: 0`. 48 hours to act; carrying
   curing salt makes the cure automatic the way the herbalist's salt rule works.
2. **At the bench, within the window**: flense → tan → oil → cut → stitch, over
   `winter-wolf-pelt` + `bog-liquor` + `neatsfoot-oil` + `sinew-thread`, product
   `cloak`. Tanning inside the chain stops the clock — no separate cure needed.
3. **Refusals avoided**: tan without the bog liquor gets *"Tan needs a tannin"*; oak
   bark would have worked too (uncommon hide, common tannin, within one tier). Waiting
   60 hours gets *"Winter Wolf Pelt has spoiled — 48 hours is the window."*
4. **Numbers**: uncommon tier, 5 stages, DC 15 + 8 = **23**; potency 1.10 from the
   oiling. Output: *Winter Wolf Cloak* — resist cold 2, frost-rimed fur, weatherproof
   sinew seams.
5. **Mastery**: 3 + 8 (four extra stages) = 11 MP, plus 2 if the skinning was risky.

### A red-dragonhide breastplate (Leatherworker 5)

The campaign's trophy piece. A red dragon's hide, dragonblood tannin, dragon sinew,
hardening wax, wyvern fat.

- **Chain**: flense → tan → oil → cut → harden → stitch → tool, product
  `armour piece`.
- **Refusals avoided**: oak bark gets *"cannot bite Red Dragonhide — the tannin must be
  within one tier of the hide"*; harden before tan gets *"raw hide in the kettle boils
  down to glue"*; anything after `tool` gets *"Tool finishes a chain."* A Leatherworker
  4 attempting it gets *"Tool is learned at Leatherworker 5"* — but the same crafter
  *without* the tool step can still work the hide, which is how the level-5 deed is
  reachable at all.
- **Numbers**: legendary tier, authored DC 30 + 12 for seven stages = **42**; potency
  1.25 × 1.10 × 1.25 ≈ 1.72. Output: *Red Dragon Armour* — resist fire 5, masterwork,
  takes enchantment, no metal in it so the party's druid can finally wear real armour.
- **Mastery**: 3 + 12 (six extra stages) = 15 MP, and the `legendary-hide` deed is
  done — level 5 unlocks the moment the points are paid.

## Integration notes

Everything this track wants from shared code but deliberately did not touch — the
rules of engagement were "write only your five files", and these are the seams left
ready:

1. **Skinning as a craft action.** `rules/leatherworker.py` exposes
   `hides_from(creature_name)` — fragment-matched against bestiary names, longest
   fragment winning — precisely so the engine's craft-action path can offer "skin the
   winter wolf" over any fallen creature in the scene and drop the right hide into
   stock with `age_hours: 0`. The foraging module's excursion shape (`rules/foraging.py`)
   is the model: skinning is to a carcass what foraging is to a biome. Wiring the
   action, the time cost and the Survival/Craft check into `rules/intents.py` and the
   scene is engine work this track did not do.

2. **Salt stops the clock automatically.** `rules/herbprep.py` already implements
   `preserve_automatically` — carrying salt cures on pickup, potency is the price. A
   skinned hide should ride the same rule; `lw.FRESH_HOURS` is pinned equal to
   `herbprep.ANIMAL_HOURS` by the tests so the two clocks cannot drift apart, but the
   automatic-cure hook is not wired.

3. **Bench UI.** `preview` returns the same shape the herbalism bench draws — problems
   list to grey the button, DC, tier, itemised effects — and takes `stock` in the same
   spirit as `crafting.preview`'s satchel. A leatherworking bench page is a rendering
   job, not a rules job. The check-terms formula (d20 + track level + half character
   level + ability) was left out of this module because the ability for leatherwork
   (Wis to match herbalism? Str for the beam? Int for the pattern?) is a design call
   the dispatcher should make once, for all tracks, not per module.

4. **Fittings come from the blacksmith.** Every `fitting` material carries
   `source: "smithed"` — buckles, studs, wire-silk's silver core. When the blacksmith
   track exists, its outputs should satisfy these material ids (or supersede them), and
   a chain that wants adamantine buckles should be able to consume the smith's actual
   stock instead of assuming a shop. The `source` field is the join key.

5. **Registry membership.** `materials()` carries its own shipped-plus-homebrew overlay
   (the `worldclass.tracks()` pattern) because adding a `materials` Kind to
   `rules/registry.py` would have touched a shared file. Folding this loader into the
   registry — one entry in `KINDS`, with the fields this module's `Material` declares —
   gives the homebrew editor a materials bench for free and deletes the local overlay.

6. **Worn-item effects.** The output's `specs` are validated effect specs, but nothing
   yet *applies* a worn item's specs to an Actor the way drunk consumables apply —
   `effectspec` itself marks resistance/DR as "applied when a creature has it". When
   worn-equipment effects land in the engine, every hide in this file starts working
   retroactively, which is why the specs are authored now rather than left as prose.
