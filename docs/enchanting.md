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

## Integration notes

*What this slice wanted from shared code and deliberately did not touch — for whoever
wires the bench.*

1. **Attaching a standing enchantment to an inventory item.** `rules/sheet.py` carries
   weapons as plain strings and consumables as `Stock` dicts; a finished binding needs a
   third shape — an item entry with a permanent `specs` list. The natural move is the
   one `consumables.Coating` made: a structure on the actor keyed by item name,
   `{"item": "Flaming Longsword", "specs": [...], "from_materials": [...]}`, consulted
   wherever buffs are summed. `Result.effects` is already exactly that list, each spec
   marked `from` and drawbacks marked `drawback: true` — nothing needs re-deriving, it
   only needs a home. The drawback specs must ride along or shadowstuff stops costing.

2. **Bench UI.** The crafting page's shape transfers whole: materials shelf (grey a
   material the chain would refuse, via the same problems list), method chips in order,
   the preview card with DC/terms/chance — plus one panel crafting does not have: the
   **mishap line**, shown before the roll, because which focus to risk is a player
   choice and `Result.mishap` already writes the sentence. The scene must supply
   `at_night` (the world clock exists for foraging) and the item's masterwork fact.

3. **Cross-craft handoff.** The masterwork gate is asserted by the caller
   (`item={"masterwork": True, "kind": "weapon"}`). When the smith and leatherworker
   tracks land their outputs as stock, their masterwork products should carry a
   `masterwork: true` field so the enchanting bench can read the fact instead of asking
   the player to vouch. The vessel entries (`requires` prose) are the catalogue of what
   to accept. Until then, the GM vouches, and an unvouched item is refused — assuming
   masterwork would wave every rusty sword through.

4. **Uniform dispatch.** `TRACK_ID`, `CraftError`, `Chain`, `preview`, `check_terms`,
   `check_bonus` deliberately mirror `rules/crafting.py`, and `materials()` mirrors
   `worldclass.tracks()`. A later `rules/benches.py` that maps track id → module can
   treat herbalism and enchanting as two entries in a dict. The one signature drift:
   enchanting's `preview(level, chain, ...)` does not take `track_id` first, because the
   module *is* the track; dispatch should pass through `TRACK_ID` rather than a free
   string.

5. **Awarding mastery.** `worldclass.award` works unchanged: `tier` from
   `Result.tier`, `stages` from `Result.stages`, `milestone` from
   `track.deed_done(tier=result.tier, success=True)`. A `risky` flag analogous to
   herbalism's could reasonably be "the working staked a fragile focus", but that is a
   design call for whoever wires the award, not a rule invented here.

6. **Registry.** Materials are not a `registry.KINDS` entry because registering one
   means touching `rules/registry.py`, which this slice must not. When someone adds a
   `"materials"` Kind (folder `materials`, key `materials`, shipped loader
   `rules.enchanter:materials`), the homebrew editor pages come free and
   `rules/enchanter.py.materials()` can collapse onto `registry.load_raw` — its own
   overlay walk is the seventh copy of the pattern the registry was written to delete,
   kept only because the alternative was editing a shared file in a parallel build.
