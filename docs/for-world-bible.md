# What Pathfinder GM needs from World Bible

**Written 2026-09-10, from the Pathfinder GM side.** The mirror of
`docs/from-world-bible.md`, which describes what World Bible hands over today. This one
describes what it does not hand over yet, in the order it would be easiest to build.

Canonical copy: `H:\coding\PathfinderGM\docs\for-world-bible.md` (under version control).
Working copy for the World Bible side: `H:\coding\WorldBible0.0\docs\for-pathfinder-gm.md`.
If they disagree, the Pathfinder GM copy is right — it sits next to the consumer that has
to eat this data.

## How to use this document

You are probably a session working in `H:\coding\WorldBible0.0`. You do not need to read
the Pathfinder GM codebase to do any of this work, and you should not need to run it.
Everything you need is here:

1. Read **The boundary** and **The GAS framework** first. They are short, and every
   schema below is shaped by them. Getting a field's *type* right and its *spirit* wrong
   is the failure mode — a `size` field containing `-2` instead of `"small"` passes JSON
   validation and breaks the consumer's whole design.
2. Pick the lowest-numbered ask that is not done.
3. Build it, ship it in the export, and check it against **Done when** at the end of that
   section.

Each ask carries: why we want it, the exact schema, a worked example against the shipped
Pangrella sample, what Pathfinder GM does today in its absence, and what "done" means.

**The consumer already reads asks 1 and 2 when they are present.** Those two are not
speculative work — write the key and the app switches from derived to authored on the next
import, with no change on our side.

---

## The boundary that must not move

`docs/campaign-format.md` states it and there is a test in the World Bible repo asserting
it: **the `play` layer carries no rules.** No levels, no stat blocks, no encounter
budgets, no dice, no DCs, no modifiers, no prices. Turning any of it into Pathfinder is
Pathfinder GM's job.

This was chosen deliberately, and it is not a limitation to route around. Baking one
ruleset into World Bible would be a promise it cannot keep — the same world should be
playable under a different ruleset by a different consumer.

So the rule for every field in every schema below:

> **World Bible supplies words. Pathfinder GM prices them.**

A people's size is `"small"`, never `-2 Strength`. A race's sight is
`"they see in the dark as well as in daylight"`, never `darkvision 60 ft.`. A situation
card's fact is a sentence the narrator may state as true, never a clock with a number on
it. If you find yourself wanting to write a number, the field is wrong — write the word
that implies it and let the consumer's own tables do the arithmetic.

There is exactly one exception, and it is not a rule: **durable ids**. Those are yours,
they are already how everything is referenced, and nothing works without them.

---

## The GAS framework, and why the shape of your data matters

Pathfinder GM's architecture converged with Unreal's **Gameplay Ability System** before
anyone here knew its name. GAS is where the design gets checked, not where it came from.
You do not need to know GAS to build any of this, but you do need to know the shape,
because it explains why every schema below looks the way it does.

### The one sentence

**The model proposes, the engine disposes.**

A local language model narrates the game. A rules engine owns every number. The model can
suggest that something happens; only the engine decides whether it did, and by how much.
Nothing a model writes lands on a character sheet without a document behind it.

### The three laws

Everything that changes a number, grants a state, or reaches the narrator obeys these.

**1. One vocabulary.** Every state anything can be in is a **hierarchical, dot-separated
tag**:

```
state.down.dead          buff.stance.blood-rage        attitude.friendly
state.fear.shaken        knows.way-past-gate           situation.world.salt-levy
holds.place.marras-house role.guard                    state.wanted.5bbd0c40345f
```

Systems ask **prefix questions** — `has_state("state.down")` answers for
`state.down.dead` and `state.down.dying` alike — and never compare condition strings.
Unknown keys self-tag, so homebrew and world-authored content participate without being
registered anywhere first.

*What this means for you:* any tag you write in an export must be dot-separated and
hierarchical, general-to-specific, lower-case, hyphens inside a segment. Put the world's
own id in the leaf when the tag is about one thing (`situation.world.salt-levy`). Never
invent a tag family that already exists under another name.

**2. One applicator.** Every change to a number travels as an **effect** — a document
with a duration, modifiers, granted tags, a stacking policy and a source. Remove the
effect and its contribution evaporates; nothing is ever "added and hopefully subtracted".
One store, one ticker, one modifier funnel.

*What this means for you:* nothing you ship is applied directly to anything. It becomes a
document the engine reads, validates, and turns into effects itself. That is why your
side can stay entirely descriptive.

**3. Severed tells.** Every effect emits a **tell** — one prose-ready sentence of what the
engine decided. The narrator is fed tells and nothing else about mechanics. Prose that
states a mechanic no tell backs is an "outcome claim" and gets cut by a scrubber.

*What this means for you:* the sentences you write in `facts[]`, `about`, `body[]` and
`senses[]` are handed to a narrator as **things it may state as true**. They must read as
prose, be self-contained, and contain no mechanics. One sentence per entry. A fact with a
digit in it is refused by the consumer's validator.

### The Rosetta, if you ever read GAS material

| GAS | Pathfinder GM |
|---|---|
| GameplayTags | the tag vocabulary (`rules/states.py`) |
| GameplayEffect | `ActiveEffect` |
| GameplayAbility | ability documents |
| AbilitySystemComponent | `Actor.apply_effect` / `Actor.tick_effects` |
| Attribute aggregator | typed modifiers + stacking channels |
| GameplayCues | tells |
| Server authority | model proposes, engine disposes |

### Deliberately refused from GAS — do not import these

- **Prediction and replication.** A third of GAS is netcode for a problem a
  single-player, single-authority, turn-based game does not have.
- **Additive-then-multiplicative aggregation.** Pathfinder 1e's typed bonuses are the
  rule instead: same named type takes the best, dodge and circumstance and untyped stack,
  penalties always stack.
- **Cosmetic fire-and-forget cues.** The presentation layer here is a language model that
  will invent a belt if you let it. Tells *constrain* the narrator; they never decorate.

### The one idea to carry into every schema below

Everything the game runs on is **a document**: a spell, a feat, a class ability, a race, a
situation card, a place, a scheme. Same grammar family, same treatment — a validator
refuses a bad one **with the fix named**, and no model ever authors a number.

When you add a list to the export, you are adding a new kind of document. It should look
like the others: a durable `id`, a human `name` or `title`, and a body made of words.

---

## Delivery: where it goes and how to ship it

Everything below is a new key inside the existing `play` object of
`<world>-campaign.json`, written by the same exporter, alongside `settlements`, `cast`,
`travel`, `conflicts` and `timeline`. Same file, same builder, same instant no-model
export.

```json
{
  "schema_version": "1.1",
  "play": {
    "settlements": [ ... ],
    "cast": [ ... ],
    "races":  [ ... ],
    "cards":  [ ... ],
    "places": [ ... ]
  }
}
```

**Bump `schema_version` MINOR for every one of these.** They only add keys, and the rule
in `docs/campaign-format.md` is ordinary semver: MINOR adds fields a consumer may ignore,
MAJOR changes or removes the meaning of an existing field and must be refused by a
consumer not written for it. None of the asks below is a MAJOR change. If you find
yourself changing the meaning of an existing field, stop and raise it — a MAJOR bump means
every existing campaign save refuses to load.

**Ids.** Every entity already carries a durable 12-character hex id. New documents get
their own ids in their own namespace: a slug is fine and preferable for things a human
will read in a file (`salt-levy`, `korvu`, `the-docks`), as long as it is unique within
the export and stable across re-exports. **Stability matters more than beauty** — a
campaign save keys off these, and an id that changes on re-export silently detaches
whatever the player had done with it.

**The export must stay a projection.** Exporting is instant and calls no model today, and
that should remain true. If a list needs generation, generate it into the world's own
files as a normal World Bible entity or section — where the author can see it, lock
fields, and regenerate it — and let the exporter project it. **Do not generate at export
time.** An export that calls a model is an export that is slow, non-deterministic, and
different every time it runs.

**Also write it to the sqlite3 sibling**, one table per list, same builder.

**How to check your work without running Pathfinder GM.** For asks 1 and 2, the consumer
falls back to deriving the list when the key is absent, so the fastest check is: does your
authored list look like a *better* version of what the fallback would have produced? The
fallbacks are described in each section. For all asks, re-export the shipped Pangrella
sample and read the JSON — it is the same world Pathfinder GM tests against
(`fixtures/pangrella-campaign.json`: 74 entities, 111 events, 5 trade routes, 5 factions,
47 characters).

---

# The asks, easiest to hardest

## 1. `play.races[]` — the world's own peoples as playable races

**Easiest by a distance. The contract is already written, the consumer already reads it,
and the underlying data already exists in every world you generate.**

### Why

A player creating a character should pick from the peoples of *this* world, not from a
generic fantasy list. World Bible already writes a `people_anatomy` section for each
`PEOPLE` — Anatomy, Body, Senses, Lifecycle. That is a race description in everything but
name. It just has no machine-readable shape, so the consumer has to guess it out of prose.

### Shape

`play.races[]`, each entry:

| Field | Meaning |
|---|---|
| `id` | durable, unique within the export (`korvu`) |
| `name` | the people's name as the world shows it |
| `people_id` | the 12-char id of the `PEOPLE` entity this is the body of |
| `size` | `small`, `medium` or `large` — **a word, not a modifier** |
| `speed` | `slow`, `normal` or `fast` — a word |
| `body[]` | short sentences about the body plan: limbs, wings, hide, what it cannot do |
| `senses[]` | short sentences about what they perceive, and in what conditions |
| `movement[]` | short sentences about how they move: climb, swim, fly, burrow |
| `about` | one paragraph, the prose a character-creation screen shows |

### Worked example, from the shipped sample

The Korvu (`fd4449bc9a64`) carry these facts today:

```
Anatomy:   Korvu have avian-like wings and bodies.
Body:      Korvu have four limbs ending in sharp talons.
Senses:    Korvu have enhanced echolocation abilities.
Lifecycle: Female Korvu give birth to 2-4 hatchlings after a 9-month gestation period
```

which should export as:

```json
{
  "id": "korvu",
  "name": "Korvu",
  "people_id": "fd4449bc9a64",
  "size": "medium",
  "speed": "normal",
  "body": [
    "They have avian bodies and broad wings.",
    "Four limbs, each ending in sharp talons."
  ],
  "senses": [
    "They hunt and navigate by echolocation, and are not troubled by the dark."
  ],
  "movement": [
    "They fly, though not for long at a stretch."
  ],
  "about": "Nomadic pastoralists of the Pangrellan grasslands, matrilineal and clan-ranked, master auramancers working in resonant crystal — and second-class citizens among the settled powers who buy their work."
}
```

Note what did *not* happen: nobody wrote `fly 30 ft. (average)`, `+2 Dex`, `low-light
vision`, or a racial point cost. The consumer's Race Builder table does all of that from
the words — `wings` in a `movement[]` sentence becomes a flight speed priced at 4 RP
against the Advanced Race Guide.

### What Pathfinder GM does today without it

`rules/races.py:from_world` derives one race per `PEOPLE` that carries an anatomy, by
running a cue table over the raw fact prose. A `PEOPLE` **without** an anatomy is offered
as a *heritage* of some other body rather than a race, which is the right call — an ethnic
group of somebody else's body is not a separate species.

It works, but it is reading sentences written for a human reader and hoping the cue words
are in them. An authored list is better because you know which peoples are meant to be
playable and which are not, and because you can say "they cannot swim" — a negative that
no cue table will ever infer.

### Done when

- Every `PEOPLE` with a `people_anatomy` section has a `play.races[]` entry.
- A `PEOPLE` without one has **no** entry (the consumer will treat it as a heritage).
- No entry contains a digit in `size`, `speed`, `body[]`, `senses[]` or `movement[]`.
- `people_id` resolves to a real entity in `entities`.
- Re-exporting twice produces identical `id`s.

---

## 2. `play.cards[]` — situation cards

**The contract is written and the consumer already reads it. Harder than races only
because it needs judgement about *which* situations matter, rather than a projection of
one entity's facts.**

### Why

A situation card is an index card of facts about one live situation, kept by the engine
and shown to the narrator whenever that situation is in play. It is how the world's own
tensions reach the table without dumping the whole world into a prompt — which does not
fit and would not be read.

The world already contains the raw material: settlement `tension`, faction `conflicts`
(aim, method, holdings, weakness), chronology events, and `unwritten` names. Nothing on a
card is invented; a card is a *selection*.

### Shape

`play.cards[]`, each entry:

| Field | Meaning |
|---|---|
| `id` | durable, unique within the export (`salt-levy`) |
| `title` | one line under 80 characters: "The salt levy is due and nobody can pay it" |
| `facts[]` | up to **eight** short sentences the narrator may state as true |
| `keys[]` | trigger words; optional — the consumer derives them from title and facts when absent |
| `tags[]` | hierarchical, dot-separated; the consumer prefixes `situation.world` to any that does not already begin with `situation.` |
| `people[]` | entity ids of the people this situation is about |
| `place` | the entity id of the settlement or region it belongs to |
| `clock` | optional; a word about how much time is left, never a number of rounds |
| `secret` | `true` if the players do not know this yet |
| `always_on` | `true` if the card should be in front of the narrator every turn, not just when triggered |

### Worked example, from the shipped sample

Pangrella (`5bbd0c40345f`) carries
`tension: "Tensions between winged nobility and merchant castes"`:

```json
{
  "id": "winged-nobility-and-the-castes",
  "title": "The winged nobility and the merchant castes are barely speaking",
  "facts": [
    "The nobility fly; the merchant castes do not, and both know what that is worth.",
    "Fine ironwork and windcatchers leave Pangrella under a noble seal.",
    "The merchant castes have the coin and none of the standing.",
    "Nothing has been said openly, which is the point."
  ],
  "keys": ["noble", "nobility", "merchant", "caste", "seal", "windcatcher"],
  "tags": ["situation.world.caste", "situation.world.pangrella"],
  "people": [],
  "place": "5bbd0c40345f",
  "clock": "",
  "secret": false,
  "always_on": true
}
```

Every one of those facts is a sentence a narrator could say out loud. None is a rule, a
number, or an instruction to the model.

### Rules for facts

- **One sentence each.** Two sentences in one entry is the commonest defect.
- **No digits.** The consumer's validator refuses a fact containing one.
- **Only names the world knows.** A fact naming a person or place that is not in
  `entities` will be refused. This matters because World Bible's own section rewrites are
  known to invent names — see **Known gaps** below.
- **True as written.** A fact is handed to the narrator as licence. "The baron may be
  lying" is a fine fact; "the baron is lying" on a non-secret card is a spoiler.
- **A secret card's facts are the truth**, and the players have not learned them yet.

### What Pathfinder GM does today without it

`rules/cards.py:from_world` derives cards from every export: the starting settlement's
strain from its own `Tension`/`Cause` facts, and one secret card per `unwritten` hook.
That is two thin sources out of a world full of them — no faction conflict becomes a card,
no chronology event does, and no settlement but the starting one.

### Done when

- The starting settlement of any world has at least one card, and it is at least as good
  as the derived one.
- Every faction in `conflicts` has produced at least one card.
- No fact contains a digit; no fact names an entity absent from `entities`.
- Cards carry `secret: true` where the players genuinely do not know, and the export's
  human-readable side does not leak them.

---

## 3. `play.places[]` — the places inside a town

**The first ask with no written contract yet, and the first that needs real generation
rather than projection. Propose the schema below or something close to it; the consumer's
existing `Place` shape is what it has to fit.**

### Why

This is the one that changes play the most.

Measured 2026-09-01 against the live saves: **a `CITY` in the current export has no
sub-places at all.** The children of Zhilvarnia in the world tree are three `CHARACTER`s.
So a city is a single point, and standing "in Pangrella" is as specific as the game can
be.

Pathfinder GM works around this with three doors — a table of implied spots read from the
settlement's own words, places the player founds in play, and ground they venture into —
and that workaround was always meant to be temporary. Its cost is that a place is
**discovered**, never **authored**: the game cannot ground the narrator against a list of
places the way it grounds it against a list of people, because there is no list.

There is one hard design constraint here, and it is settled, so do not design against it:

> **World Bible cannot author every place, and Pathfinder GM must still be able to make
> one during play. One format, two authors.**

Whatever you ship must be the *same shape* the app writes when the fiction reaches
somewhere nobody authored. That is why the schema below carries an `origin` field.

### Shape

`play.places[]`, each entry:

| Field | Meaning |
|---|---|
| `id` | durable and unique within the export. Prefix with the settlement id so two towns may both have a market: `5bbd0c40345f:the-market` |
| `name` | what people call it, lower case, article included: `"the market"`, `"the mine head"` |
| `about` | one short sentence: what it is for, what it is like. Prose the narrator may use |
| `parent` | the 12-char entity id of the settlement or region containing it |
| `terrain` | one word — `urban`, `forest`, `hills`, `coast`, `underground`, … |
| `exits[]` | the ids of the places you can walk to from here. **Adjacency only, no distances or weights** |
| `described_only` | `true` for a place that is named in prose but cannot be entered — "an alley runs east" — so the narrator may mention it without the engine minting a node |
| `origin` | always `"world"` for anything you export. The app writes `"found"` or `"venture"` for its own |

**Do not ship distances or weighted borders.** Fate shipped weighted zone borders and then
deleted them; the consumer refuses them by design, and obstruction belongs in states and
effects rather than a cost table nobody would tune.

### Worked example

```json
[
  {"id": "5bbd0c40345f:the-market", "name": "the market",
   "about": "Windcatchers turning over every stall, and ironwork under noble seal.",
   "parent": "5bbd0c40345f", "terrain": "urban",
   "exits": ["5bbd0c40345f:the-gate", "5bbd0c40345f:the-workshops"],
   "described_only": false, "origin": "world"},

  {"id": "5bbd0c40345f:the-workshops", "name": "the workshops",
   "about": "Where the trades are, and where the castes outnumber the nobility.",
   "parent": "5bbd0c40345f", "terrain": "urban",
   "exits": ["5bbd0c40345f:the-market"],
   "described_only": false, "origin": "world"}
]
```

### What a settlement needs at minimum

The consumer's fallback table produces roughly this set, and an authored one should not be
poorer: somewhere to buy (**the market**), somewhere to sleep (**the tavern** or lodging),
somewhere to leave by (**the gate**), somewhere quiet (**the temple** or shrine), somewhere
the trades are (**the workshops**), and somewhere nobody is watching (**the back streets**).
Then whatever this particular town actually has — a port town gets **the docks**, a mining
town **the mine head**, a river town **the bridge**.

The world's own words should drive the extras. Vyrakon's export says "port access" and
"cyclone-prone coastlines"; a settlement with those words in its facts should have a
harbour, and the reason the consumer built an implied-spot table at all was a session
asking "why did it not make a docks?"

**Every place must be reachable.** A place with an empty `exits[]` that nothing else exits
to is a place no party can stand in.

### What Pathfinder GM does today without it

Three doors, all staying regardless of what you ship:

1. **Implied** — a fixed table of cue words read from the settlement's own facts
   (`port`/`harbour`/`quay` → the docks; `mine`/`quarry`/`ore` → the mine head), plus a
   generated base set per settlement scale.
2. **Founded** — the player declares a base ("we set up at Marra's house") and the engine
   mints it with an owner.
3. **Ventured** — ground gone into (the sewers, a cave) generated from a seed.

Authored places would replace door one and leave doors two and three exactly as they are.

### Done when

- Every `CITY` in the sample world has at least four places, all mutually reachable.
- Place ids are stable across two consecutive exports.
- Every `parent` resolves to a real entity; every id in `exits[]` resolves to a real place.
- Settlements whose facts mention a port, a mine, a river or a library have the matching
  place.
- No place carries a distance, a travel time, or a numeric weight.

---

## 4. Resources, materials and ingredients

**The largest gap between "what the world says" and "what the game can use", and the ask
that most needs a conversation before code.**

### Why

The export already tells us what a town trades. Pangrella:

```json
"sells": "Fine ironwork and crafted windcatchers",
"buys":  "Luminous crystals from Khra'gixx caverns"
```

**Nothing in Pathfinder GM reads those two fields.** They are free prose, and the game's
market shelf comes from `content/materials` — the app's own built-in tables, identical in
every world. So a world can be about the salt trade and the game will still sell you the
same quicklime it sells everywhere.

This is the ask from 2026-09-01: *resources, materials and ingredients, derived from the
generated world and formatted to ship straight in.*

### The hard part, stated plainly

Every other ask on this list is a shape problem. This one is a **shared vocabulary**
problem, and that is why it is fourth rather than second.

For a town's `sells` to mean something mechanically, both sides have to agree on what a
thing *is*. Pathfinder GM already has a materials shelf with ids, prices and crafting
uses, shared across four crafting benches. World Bible generates prose. Bridging them is
one of:

- **(a) World Bible names its resources from a shared list.** Precise, immediately usable,
  and it drags a rules-adjacent vocabulary into World Bible — which brushes against the
  boundary rule.
- **(b) World Bible ships its resources as documents with descriptive words, and the
  consumer maps them onto its own shelf** the way it already maps a people's anatomy onto
  the Race Builder. Keeps the boundary clean; a mapping layer can always be wrong.
- **(c) Both: a resource document carries the world's own words *and* an optional
  `kind` from a small, stable, deliberately rules-free vocabulary** (`ore`, `stone`,
  `timber`, `hide`, `cloth`, `herb`, `crystal`, `salt`, `grain`, `spice`, `oil`, `dye`).

**(c) is the recommendation.** The `kind` list is a dozen nouns any world has, it is not
Pathfinder-specific, it does not carry a price or a DC, and it gives the consumer enough
to route a resource onto the right bench without guessing from prose.

### Proposed shape, to be agreed before building

`play.resources[]`:

| Field | Meaning |
|---|---|
| `id` | durable, unique (`resonant-crystal`) |
| `name` | the world's own name for it |
| `kind` | one word from the small vocabulary above |
| `about` | one sentence: what it is and what it is good for |
| `found_at[]` | entity ids of settlements or regions that produce it |
| `wanted_at[]` | entity ids that buy it |
| `rarity` | `common`, `uncommon` or `rare` — **a word** |

and a corresponding change to `play.settlements[]`, keeping the prose and adding ids:

```json
"sells": "Fine ironwork and crafted windcatchers",
"sells_ids": ["ironwork", "windcatcher"],
"buys": "Luminous crystals from Khra'gixx caverns",
"buys_ids": ["resonant-crystal"]
```

Additive, so no MAJOR bump and no existing consumer breaks.

### What Pathfinder GM does today without it

`rules/market.py:everything_priced` builds the stall shelf from every material any bench
prices, deduplicated — the app's own content, world-independent. Trade routes are read for
travel, not for goods.

### Done when

- The bridging approach is **agreed with the user** before any code is written.
- Every settlement's `sells`/`buys` prose has at least one corresponding id.
- Every id in `sells_ids`/`buys_ids` resolves to a `play.resources[]` entry.
- No resource carries a price, a weight in pounds, a craft DC, or a rarity number.

---

## 5. `play.schemes[]` — quests as documents

**Hardest, and deliberately last. Pathfinder GM has explicitly ordered this after
hand-written schemes have been played end to end in both worlds. Do not start it before
then.**

### Why it is last

A scheme is the richest document in the system: slots, storylet steps with tag-query
criteria, outcomes with effects, and a fairness contract about foreshadowing. The plan
(`docs/quest-schemes-plan.md`, build order §6.10) is explicit — hand-written schemes in
`content/schemes/`, played through in both worlds, and *only then* schemes in the export.

There is a second, firmer constraint: **never the watcher.** The off-turn model that
advances situation cards must not author schemes. A scheme is authored content, by a human
or by World Bible's own generation with an author reviewing it — never improvised by a
model mid-play.

### Shape, for when the time comes

| Field | Meaning |
|---|---|
| `id`, `title`, `about` | `about` is for the editing bench, never shown to the narrator |
| `slots` | roles and places **with no names** — `{"role": "giver", "wants": {...}}` |
| `cards` | the visible quest card(s) and the secret card(s) it opens, with `$slot` placeholders |
| `steps` | storylets: `{id, criteria[], action, tell, once}` |
| `outcomes` | named endings, their effects, and what they open next |
| `fairness` | which tags the brief must have carried before a twist may fire |

The load-bearing idea is **slots**. A scheme names no one. It says "a giver who wants
something kept quiet" and "a place to sleep", and the consumer fills those from the
world's own cast and places at the moment the scheme opens, then freezes them. That is
what lets one scheme run in any world — and it is why asks 1–4 come first: a scheme is
only as good as the cast, places and resources it can draw on.

### Done when

Not applicable yet. Revisit once Pathfinder GM reports hand-written schemes played end to
end in two different worlds.

---

## 6. `play.travel[].miles` — how far apart two settlements are

**The one ask that adds a number to the `play` layer, and the reasoning for the exception
is below. Small, entirely optional, and the app already works without it.**

### Why

Pathfinder GM can now leave a town. Until 2026-09-14 it could not: `Scene.location_id` was
written once when a campaign began and never again, so a world shipping twelve settlements
was played in exactly one of them. There is a `journey` op now, and it charges the road to
the clock — days pass, the body gets thirsty, effects expire, the world moves on.

What it cannot do is know how long the road is. A route in the export carries `carrying`
and `friction`, both prose. So the app answers in one of two ways:

- **exact** — the world said how many miles, and Pathfinder 1e's overland table does the
  arithmetic against the traveller's speed and the ground;
- **derived** — it did not, and the time comes from how far apart the two settlements sit
  in the world's own containment tree. That answer is reported to the player in **days on
  the road and never in miles**, because a mileage nobody wrote down would be this app
  inventing a fact about your world.

Derived is perfectly playable. Exact is better, and it is three optional fields.

### Shape

Additive to the entries already in `play.travel[]`:

| Field | Meaning |
|---|---|
| `miles` | integer, the length of the road. Crow-flight or road, whichever you mean — say which once, in the contract, not per record |
| `road` | one of `highway`, `road`, `trail`, `none`. This is the column Pathfinder's overland table needs and neither program has |
| `crosses[]` | the terrain the route passes through, in your own words — `forest`, `hills`, `swamp`. The consumer maps them to its own and says so when it cannot |

```json
{"from_id": "58b90a214ada", "to_id": "5bbd0c40345f",
 "from": "Zhilgoroth", "to": "Pangrella",
 "carrying": "Resonant crystal; high-quality winged livestock",
 "friction": "...",
 "miles": 90, "road": "road", "crosses": ["hills", "forest"]}
```

### Why this is allowed to be a number, when rule 1 says not to write numbers

Rule 1 in "What not to do" forbids numbers in the `play` layer, and every example it gives
is a **rules** quantity — sizes as modifiers, speeds in feet, clocks in rounds, prices,
DCs, rarity as a percentage. A distance between two towns is not one of those. It is the
same kind of fact as a settlement's `scale` or its terrain: true regardless of which game
reads it, and expressible without a word of Pathfinder vocabulary.

Rule 2 is untouched. Every conversion — miles to hours, terrain to a multiplier, an extra
hour of marching to a Constitution check — happens on Pathfinder GM's side of the file.
**Do not ship hours or days.** Those depend on who is walking, which is the consumer's
business and not yours.

### What not to do

- **Do not add coordinates.** `agent_engine/world_map.py` is a containment diagram — ring
  radius encodes depth in the tree, and the module says so itself: "a claim about
  structure, not about latitude". Exporting those x/y as geography would produce confident,
  precise, wrong distances, and nothing downstream would look wrong.
- **Do not guess a length.** An absent `miles` is handled honestly. A made-up one is not
  recoverable, because the consumer cannot tell it from a real one.
- **Do not weight the edges inside a town.** The town map's "adjacency only, and the save
  refuses a distance" rule stays exactly as it is. Which room you are in is a discrete
  fact; how far the market is from the gate in feet is not a number the world file needs.

### Done when

An export carries `miles` on at least one route, Pathfinder GM reports that journey as
`exact`, and the tell names the distance instead of only the days.

---

# Known gaps — not asks yet, but on the list

These are documented in `docs/from-world-bible.md` and Pathfinder GM codes defensively
around them. None is urgent. All would be welcome.

- **No maps, coordinates or distances.** Places relate by containment and trade, not
  geometry. Encounter maps are generated rather than imported, and that stays true — a
  place's floor plan is derived from its own durable id, so the same room is the same room
  in every session without a byte of it crossing the file.
  **Travel time is no longer invented in the dark**: ask 6 above asks for `miles` on the
  routes you already write, and until it arrives a journey is timed from the containment
  tree and reported in days rather than miles. If full geometry ever appears, say so before
  shipping it — "distance exists now" changes how travel and encounters work.
- **`entity_id` can be `null`** on a chronology figure or a trade-route endpoint: named,
  never written up. Collected in `unwritten`, which Pathfinder GM turns into secret cards
  — so this gap is currently *useful*, and closing it entirely would remove a source of
  hooks. Better: keep `unwritten` and make it exhaustive.
- **`unwritten` is not exhaustive.** Missing-place detection only reads structured fields,
  so a place invented purely inside a faction's prose is never caught.
- **Section rewrites can invent places and people.** The faction rebuild is grounded
  against the world's real names; a section rewrite is not. One produced "Aviari's Spire"
  and "Elyria's Forge", neither of which exists. This is the gap that most affects the
  asks above — an invented name reaching a situation card is refused by the consumer's
  validator, so ungrounded rewrites turn directly into dropped cards.
- **Years can be `null`** for undated events; the timeline sorts those last.

---

# What not to do

A short list, because each of these would cost a rework rather than a fix.

1. **Do not write numbers into the `play` layer.** Not sizes as modifiers, not speeds in
   feet, not clocks in rounds, not prices, not DCs, not rarity as a percentage.
2. **Do not bake Pathfinder vocabulary into World Bible.** No `darkvision`, no `CR`, no
   `1d6`, no ability score names. There is a test in the World Bible repo asserting this
   and it should stay passing.
3. **Do not generate at export time.** Generate into the world's files where the author
   can see and lock it; the exporter projects.
4. **Do not let ids change between exports.** A campaign save keys off them.
5. **Do not make a MAJOR schema bump** to add any of this. Every ask here is additive.
6. **Do not design places as discovery-only or authored-only.** Both routes are permanent
   and that is a settled decision.
7. **Do not have a model author a scheme, ever.**

---

# Summary

| # | Ask | Contract | Consumer ready | Effort |
|---|---|---|---|---|
| 1 | `play.races[]` | written | **yes — reads it today** | small |
| 2 | `play.cards[]` | written | **yes — reads it today** | small–medium |
| 3 | `play.places[]` | proposed here | no — needs the key wired up | medium |
| 4 | resources / materials | proposed here, needs agreement | no | large |
| 5 | `play.schemes[]` | sketched | no — and blocked on our side | largest |

Asks 1 and 2 are the ones to do first, and not only because they are easiest: the consumer
already reads both, so each one flips from derived to authored the day it appears in an
export, with no coordinated release and nothing to change on the Pathfinder GM side.
